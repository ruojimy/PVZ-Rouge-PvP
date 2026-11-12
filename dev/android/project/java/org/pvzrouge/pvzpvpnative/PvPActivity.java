package org.pvzrouge.pvzpvpnative;

import org.libsdl.app.SDLActivity;

/** The whole game is libmain.so (src/app/main.cpp, SDL_main); this only names the native libraries. */
public class PvPActivity extends SDLActivity {
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
