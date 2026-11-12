// Private native stdio bridge. Included only by the two file adapters.
#pragma once
#include "core/value.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <filesystem>
#include <string>
#include <system_error>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#include <sys/stat.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

namespace pvz::native_file {
[[noreturn]] inline void error(const char* operation, int code = errno) {
    if (!code) code = EIO;
    const char* kind = code == ENOENT ? "FileNotFoundError" : code == EEXIST ? "FileExistsError" :
        (code == EACCES || code == EPERM) ? "PermissionError" : "OSError";
    throw PyError(kind, std::string(operation) + ": " + std::generic_category().message(code));
}
#ifdef _WIN32
// _commit on a stale/out-of-range descriptor invokes the CRT policy before
// returning EBADF. Suppress that termination on this thread and restore it.
struct InvalidParameterGuard {
    _invalid_parameter_handler previous;
    static void ignore(const wchar_t*, const wchar_t*, const wchar_t*, unsigned int, uintptr_t) {}
    InvalidParameterGuard() : previous(_set_thread_local_invalid_parameter_handler(ignore)) {}
    ~InvalidParameterGuard() { _set_thread_local_invalid_parameter_handler(previous); }
};
#endif
inline void sync(int descriptor) {
    if (descriptor < 0) error("fsync", EBADF);
    int status, code;
    {
#ifdef _WIN32
        InvalidParameterGuard guard;
        status = _commit(descriptor);
#else
        do { status = ::fsync(descriptor); } while (status != 0 && errno == EINTR);
#endif
        code = errno;
    }
    if (status != 0) error("fsync", code);
}

class File {
    std::FILE* stream_ = nullptr;
    bool readable_ = false, writable_ = false;
    enum class Last { none, read, write } last_ = Last::none;
    void require_open() const {
        if (!stream_) throw PyError("ValueError", "I/O operation on closed file");
    }
    void before_read() {
        require_open();
        if (!readable_) error("file is not open for reading", EBADF);
        if (last_ == Last::write && std::fflush(stream_) != 0) error("file flush before read");
        last_ = Last::read;
    }
    void before_write() {
        require_open();
        if (!writable_) error("file is not open for writing", EBADF);
        if (last_ == Last::read) seek(0, SEEK_CUR);
        last_ = Last::write;
    }
public:
    File() = default;
    File(const File&) = delete;
    File& operator=(const File&) = delete;
    ~File() { if (stream_) std::fclose(stream_); }
    bool is_open() const { return stream_ != nullptr; }
    void open(const std::filesystem::path& path, const std::string& mode) {
        char base = 0; bool plus = false;
        for (char c : mode) {
            if (c == 'r' || c == 'w' || c == 'a' || c == 'x') {
                if (base) throw PyError("ValueError", "invalid file mode");
                base = c;
            } else if (c == '+') {
                if (plus) throw PyError("ValueError", "invalid file mode");
                plus = true;
            } else if (c != 'b' && c != 't') throw PyError("ValueError", "invalid file mode");
        }
        if (!base || stream_) throw PyError("ValueError", "invalid file mode or file already open");
        readable_ = base == 'r' || plus;
        writable_ = base != 'r' || plus;
        std::string normalized(1, base == 'x' ? 'w' : base);
        if (plus) normalized += '+';
        normalized += 'b'; // Preserve the adapters' physical UTF-8/binary I/O.
        int fd;
#ifdef _WIN32
        int flags = _O_BINARY | _O_NOINHERIT | (plus ? _O_RDWR : base == 'r' ? _O_RDONLY : _O_WRONLY);
        if (base != 'r') flags |= _O_CREAT;
        if (base == 'w') flags |= _O_TRUNC;
        if (base == 'a') flags |= _O_APPEND;
        if (base == 'x') flags |= _O_EXCL;
        fd = _wopen(path.c_str(), flags, _S_IREAD | _S_IWRITE);
        if (fd < 0) error("open file");
        stream_ = _fdopen(fd, normalized.c_str());
        if (!stream_) { int code = errno; _close(fd); error("fdopen file", code); }
#else
        int flags = O_CLOEXEC | (plus ? O_RDWR : base == 'r' ? O_RDONLY : O_WRONLY);
        if (base != 'r') flags |= O_CREAT;
        if (base == 'w') flags |= O_TRUNC;
        if (base == 'a') flags |= O_APPEND;
        if (base == 'x') flags |= O_EXCL;
        do { fd = ::open(path.c_str(), flags, 0666); } while (fd < 0 && errno == EINTR);
        if (fd < 0) error("open file");
        stream_ = ::fdopen(fd, normalized.c_str());
        if (!stream_) { int code = errno; ::close(fd); error("fdopen file", code); }
#endif
        if (base == 'a') seek(0, SEEK_END);
    }
    int descriptor() const {
        require_open();
#ifdef _WIN32
        int fd = _fileno(stream_);
#else
        int fd = ::fileno(stream_);
#endif
        if (fd < 0) error("file fileno");
        return fd;
    }
    size_t write(const std::string& data) {
        before_write();
        size_t count = std::fwrite(data.data(), 1, data.size(), stream_);
        if (count != data.size()) error("file write");
        return count;
    }
    std::string read(int64_t limit = -1) {
        before_read();
        std::string data; char buffer[8192];
        while (limit < 0 || static_cast<int64_t>(data.size()) < limit) {
            size_t wanted = sizeof(buffer);
            if (limit >= 0 && limit - static_cast<int64_t>(data.size()) < static_cast<int64_t>(wanted))
                wanted = static_cast<size_t>(limit - static_cast<int64_t>(data.size()));
            size_t count = std::fread(buffer, 1, wanted, stream_);
            data.append(buffer, count);
            if (count < wanted) {
                if (std::ferror(stream_)) error("file read");
                break;
            }
        }
        return data;
    }
    std::string readline(int64_t limit = -1) {
        before_read();
        std::string line;
        while (limit < 0 || static_cast<int64_t>(line.size()) < limit) {
            int c = std::fgetc(stream_);
            if (c == EOF) { if (std::ferror(stream_)) error("file readline"); break; }
            line += char(c);
            if (c == '\n') break;
        }
        return line;
    }
    void flush() {
        require_open();
        if (last_ == Last::read) { seek(0, SEEK_CUR); return; }
        if (std::fflush(stream_) != 0) error("file flush");
    }
    int64_t tell() const {
        require_open();
#ifdef _WIN32
        auto offset = _ftelli64(stream_);
#else
        auto offset = ::ftello(stream_);
#endif
        if (offset < 0) error("file tell");
        return static_cast<int64_t>(offset);
    }
    int64_t seek(int64_t offset, int whence = SEEK_SET) {
        require_open();
        if ((whence != SEEK_SET && whence != SEEK_CUR && whence != SEEK_END) || (whence == SEEK_SET && offset < 0))
            error("file seek", EINVAL);
#ifdef _WIN32
        int status = _fseeki64(stream_, offset, whence);
#else
        int status = ::fseeko(stream_, static_cast<off_t>(offset), whence);
#endif
        if (status != 0) error("file seek");
        last_ = Last::none;
        return tell();
    }
    void close() {
        if (!stream_) return;
        std::FILE* closing = stream_; stream_ = nullptr;
        if (std::fclose(closing) != 0) error("file close");
    }
};
} // namespace pvz::native_file
