package org.pvzrouge.pvzpvpnative;

import org.libsdl.app.SDLActivity;

/** The whole game is libmain.so (src/app/main.cpp, SDL_main); this only names the native libraries. */
public class PvPActivity extends SDLActivity {
    private volatile String texturePicked = "";
    private String textureExport = "";
    public void chooseTextureFile(final boolean pack) {
        runOnUiThread(() -> {
            android.content.Intent i = new android.content.Intent(android.content.Intent.ACTION_OPEN_DOCUMENT);
            i.addCategory(android.content.Intent.CATEGORY_OPENABLE);
            i.setType(pack ? "*/*" : "image/*");
            startActivityForResult(i, 7401);
        });
    }
    public void exportTextureFile(final String path) {
        runOnUiThread(() -> {
            textureExport = path;
            android.content.Intent i = new android.content.Intent(android.content.Intent.ACTION_CREATE_DOCUMENT);
            i.addCategory(android.content.Intent.CATEGORY_OPENABLE);
            i.setType(path.endsWith(".png") ? "image/png" : "application/json");
            i.putExtra(android.content.Intent.EXTRA_TITLE, new java.io.File(path).getName());
            startActivityForResult(i, 7402);
        });
    }
    public synchronized String pollTextureFile() {
        String p = texturePicked; texturePicked = ""; return p;
    }
    @Override
    protected void onActivityResult(int request, int result, android.content.Intent data) {
        super.onActivityResult(request, result, data);
        if ((request != 7401 && request != 7402) || result != RESULT_OK || data == null || data.getData() == null) return;
        final android.net.Uri uri = data.getData();
        new Thread(() -> {
            try {
                if (request == 7402) {
                    try (java.io.InputStream in = new java.io.FileInputStream(textureExport);
                         java.io.OutputStream out = getContentResolver().openOutputStream(uri)) {
                        byte[] b = new byte[16384]; int n;
                        while ((n = in.read(b)) != -1) out.write(b, 0, n);
                    }
                    return;
                }
                String name = "image.png";
                try (android.database.Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) {
                        int at = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                        if (at >= 0) name = cursor.getString(at);
                    }
                }
                boolean pack = name.endsWith(".pvptex") || name.endsWith(".json");
                java.io.File target = new java.io.File(getFilesDir(), "texture-import-" + System.nanoTime() + (pack ? ".pvptex" : ".png"));
                try (java.io.InputStream in = getContentResolver().openInputStream(uri);
                     java.io.OutputStream out = new java.io.FileOutputStream(target)) {
                    byte[] b = new byte[16384]; int n; long total = 0;
                    while ((n = in.read(b)) != -1) {
                        total += n; if (total > 32L * 1024 * 1024) throw new java.io.IOException("文件超过 32 MB");
                        out.write(b, 0, n);
                    }
                }
                synchronized (this) { texturePicked = target.getAbsolutePath(); }
            } catch (Exception e) {
                synchronized (this) { texturePicked = "!" + e.getMessage(); }
            }
        }, "PvP-texture-file").start();
    }
    @Override
    protected String[] getArguments() {
        if(getIntent().getBooleanExtra("pvp72_trace_ui",false))
            SDLActivity.nativeSetenv("PVZ72_TRACE_UI","1");
        String encoded=getIntent().getStringExtra("pvp72_diagnostic_b64");
        if(encoded==null)return new String[0];
        if(encoded.length()>32768)throw new IllegalArgumentException("Diagnostic config too large");
        String json=new String(android.util.Base64.decode(encoded,android.util.Base64.DEFAULT),java.nio.charset.StandardCharsets.UTF_8);
        // SDLMain calls getArguments after libraries load, before SDL_main.
        // Enable counters only for an explicit diagnostic in a fresh process.
        if(getIntent().getBooleanExtra("pvp72_render_stats",false))
            SDLActivity.nativeSetenv("PVZ72_RENDER_STATS","1");
        return new String[]{"--diagnostic-json",json};
    }
    @Override
    protected String[] getLibraries() {
        return new String[] { "SDL2", "SDL2_image", "SDL2_mixer", "SDL2_ttf", "main" };
    }
}
