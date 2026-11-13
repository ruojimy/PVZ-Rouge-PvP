#include "ui/hand/texture74_internal.h"
#include "core/fsutil.h"
#include <algorithm>
#ifdef _WIN32
#include <windows.h>
#include <commdlg.h>
#endif
#ifdef __ANDROID__
#include <jni.h>
#include <SDL_system.h>
#endif
namespace pvz::texture74 {
std::string choose_file(bool save,const std::string& suggested,bool pack){
#ifdef _WIN32
 wchar_t file[32768]{};auto value=u8p(suggested).wstring();std::copy_n(value.data(),std::min(value.size(),size_t(32767)),file);
 OPENFILENAMEW d{};d.lStructSize=sizeof(d);d.lpstrFile=file;d.nMaxFile=32768;
 d.lpstrFilter=pack?L"PvP 材质包 (*.pvptex;*.json)\0*.pvptex;*.json\0所有文件\0*.*\0":L"图片 (PNG/JPG/BMP)\0*.png;*.jpg;*.jpeg;*.bmp\0PvP 材质包\0*.pvptex;*.json\0所有文件\0*.*\0";
 if(save&&!pack)d.lpstrFilter=L"PNG 图片 (*.png)\0*.png\0所有文件\0*.*\0";
 d.lpstrTitle=save?(pack?L"导出 PvP 材质包":L"导出透明 PNG"):L"导入图片或 PvP 材质包";d.Flags=OFN_EXPLORER|OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST|(save?OFN_OVERWRITEPROMPT:OFN_FILEMUSTEXIST);d.lpstrDefExt=save?(pack?L"pvptex":L"png"):nullptr;
 if(save?GetSaveFileNameW(&d):GetOpenFileNameW(&d))return p8(std::filesystem::path(file));return {};
#elif defined(__ANDROID__)
 if(save)return suggested;auto* env=(JNIEnv*)SDL_AndroidGetJNIEnv();auto activity=(jobject)SDL_AndroidGetActivity();if(!env||!activity)return {};
 jclass cls=env->GetObjectClass(activity);auto method=env->GetMethodID(cls,"chooseTextureFile","(Z)V");if(method)env->CallVoidMethod(activity,method,jboolean(pack));if(env->ExceptionCheck())env->ExceptionClear();env->DeleteLocalRef(cls);env->DeleteLocalRef(activity);return {};
#else
 set_notice("请将图片放入材质包目录，或拖入游戏窗口");return save?suggested:std::string{};
#endif
}
void android_export(const std::filesystem::path& path){
#ifdef __ANDROID__
 auto* env=(JNIEnv*)SDL_AndroidGetJNIEnv();auto activity=(jobject)SDL_AndroidGetActivity();if(!env||!activity)return;auto cls=env->GetObjectClass(activity);auto method=env->GetMethodID(cls,"exportTextureFile","(Ljava/lang/String;)V");if(method){auto str=env->NewStringUTF(p8(path).c_str());env->CallVoidMethod(activity,method,str);env->DeleteLocalRef(str);}if(env->ExceptionCheck())env->ExceptionClear();env->DeleteLocalRef(cls);env->DeleteLocalRef(activity);
#endif
}
std::string poll_file(){
#ifdef __ANDROID__
 auto* env=(JNIEnv*)SDL_AndroidGetJNIEnv();auto activity=(jobject)SDL_AndroidGetActivity();if(!env||!activity)return {};auto cls=env->GetObjectClass(activity);auto method=env->GetMethodID(cls,"pollTextureFile","()Ljava/lang/String;");std::string out;if(method){auto str=(jstring)env->CallObjectMethod(activity,method);if(str){const char* text=env->GetStringUTFChars(str,nullptr);if(text){out=text;env->ReleaseStringUTFChars(str,text);}env->DeleteLocalRef(str);}}if(env->ExceptionCheck())env->ExceptionClear();env->DeleteLocalRef(cls);env->DeleteLocalRef(activity);return out;
#else
 return {};
#endif
}
}
