// Actual original callback; PYC SHA6f10bada...; entry34910, returns36188/36234.
// Bare-except at35420..35454 recovered from the pinned disassembly.
void region_menu_callback(Match& G) {
    if (((attr(G.event, SV("type")) == G.pygame_attr(SV("MOUSEBUTTONUP"))) && (G.global(V("选中")) != V(-1.0)) && !py::in(SV("提示"), rd(G.选块, G.global(V("选中")))))) {
        (void)call(G.播音, SV("选中"));
        G.选块名 = V::list({});
        G.name = call(G.c, rdm(rd(G.选块, G.global(V("选中"))), &Obj::名, SV("名")));
        if (py::in(G.name, G.设置)) {
            if (((G.name == SV("屏幕大小")) || (G.name == SV("全屏")))) {
                wr(G.global(V("挪动")), V(4.0)) = V(0.0);
                if ((G.name == SV("全屏"))) {
                    if ((rd(G.设置, G.name)).truthy()) {
                        wr(G.设置, SV("屏幕大小")) = V(2.0);
                        wr(G.设置, G.name) = V(false);
                    } else {
                        wr(G.设置, SV("屏幕大小")) = V(0.0);
                        wr(G.设置, G.name) = V(true);
                    }
                } else {
                    wr(G.设置, SV("全屏")) = V(false);
                    wr(G.设置, G.name) += V(1.0);
                    if ((rd(G.设置, G.name) == V(5.0))) {
                        wr(G.设置, G.name) = V(1.0);
                    }
                }
                if ((rd(G.设置, SV("屏幕大小")) == V(0.0))) {
                    G.总宽 = G.global(V("原总宽"));
                    G.总高 = G.global(V("原总高"));
                    G.screen = callm(G.pygame_attr(SV("display")), SY("set_mode"), Args{V::tuple({G.总宽, G.总高}), G.pygame_attr(SV("FULLSCREEN"))});
                    (void)call(G.加载游戏);
                } else {
                    G.总宽 = floordiv((G.global(V("原总宽")) * (V(5.0) - rd(G.设置, SV("屏幕大小")))), V(5.0));
                    G.总高 = floordiv((G.global(V("原总高")) * (V(5.0) - rd(G.设置, SV("屏幕大小")))), V(5.0));
                    G.screen = callm(G.pygame_attr(SV("display")), SY("set_mode"), Args{V::tuple({G.总宽, G.总高})});
                    (void)call(G.加载游戏);
                }
                (void)call(G.选块归位);
            } else if ((py::in(G.name, V::tuple({SV("音乐"), SV("音效")})) && (G.global(V("没音"))).truthy())) {
            } else if ((rd(G.设置, G.name)).truthy()) {
                wr(G.设置, G.name) = V(false);
                if ((G.name == SV("音乐"))) {
                    (void)callm(attr(G.pygame_attr(SV("mixer")), SV("music")), SY("set_volume"), Args{V(0.0)});
                }
            } else {
                wr(G.设置, G.name) = V(true);
                if ((G.name == SV("音乐"))) {
                    (void)callm(attr(G.pygame_attr(SV("mixer")), SV("music")), SY("set_volume"), Args{V(0.4)});
                }
            }
        }
        if (((rd(G.name, V(-1.0)) == SV("式")) || (G.name == SV("我是僵尸")))) {
            (void)call(G.音乐淡出);
            (void)call(G.播音, SV("开始游戏"));
            try {
                (void)callm(rd(G.音效, SV("开始游戏")), SY("set_volume"), Args{V(0.2)});
            } catch (const PyError&) {
            }
            G.关 = V(1.0);
            G.选块名 = V::list({SV("空")});
            G.模式 = G.name;
        }
        if ((G.name == SV("离开"))) {
            (void)call(G.关游戏);
        }
        if ((G.name == SV("花园"))) {
            G.开始方式 = SV("花园");
            G.关 = V(1.0);
            G.选块名 = V::list({SV("空")});
            (void)call(G.音乐淡出);
        }
        if ((G.name == SV("继续游戏"))) {
            G.开始方式 = SV("继续游戏");
            { V it1_ = py::iter_list(rd(G.数据, SV("继续")));
            for (size_t i1_ = 0; i1_ < it1_.len(); ++i1_) {
                G.l = it1_.idx(int64_t(i1_));
                (void)G.选块名.append(G.l);
            }}
        }
        if (((G.name == SV("WAD")) || (G.name == SV("空AD")) || (G.name == SV("↑←→")))) {
            wr(G.设置, SV("按键")) = G.name;
        }
        if ((G.name == SV("皮肤"))) {
            G.选块名 = V::list({SV("返回"), SV("疯狂戴夫"), SV("我的世界"), SV("结束乐队"), SV("调查兵团")});
        }
        if ((G.name == SV("声明"))) {
            G.选块名 = V::list({SV("返回"), SV("作者"), SV("空"), SV("空"), SV("空")});
        }
        if ((G.name == SV("按键设置"))) {
            G.选块名 = V::list({SV("返回"), SV("空AD"), SV("WAD"), SV("↑←→")});
        }
        if ((G.name == SV("屏幕设置"))) {
            G.选块名 = V::list({SV("返回"), SV("全屏"), SV("屏幕大小")});
        }
        if ((G.name == SV("设置"))) {
            G.选块名 = V::list({SV("返回"), SV("音效"), SV("音乐"), SV("屏幕设置"), SV("粒子效果"), SV("按键设置")});
        }
        if ((G.name == SV("新游戏"))) {
            G.开始方式 = SV("新游戏");
            G.选块名 = V::list({SV("正常模式"), SV("未-极难模式"), SV("未-抽奖模式"), SV("未-末日模式"), SV("未-我是僵尸")});
            if ((py::in(SV("正常模式"), rd(G.数据, SV("打败boss"))) || (G.版本 == SV("v-1.0.0")) || (G.版本 == SV("v233.0.0")))) {
                wr(G.选块名, V(1.0)) = SV("极难模式");
            }
            if ((py::in(SV("极难模式"), rd(G.数据, SV("打败boss"))) || (G.版本 == SV("v-1.0.0")) || (G.版本 == SV("v233.0.0")))) {
                wr(G.选块名, V(3.0)) = SV("末日模式");
            }
            if ((py::in(SV("抽奖模式"), rd(G.数据, SV("打败boss"))) || (G.版本 == SV("v-1.0.0")) || (G.版本 == SV("v233.0.0")))) {
                wr(G.选块名, V(4.0)) = SV("我是僵尸");
            }
            if (((py::len(G.global(V("杯子"))) > V(0.0)) || (py::in(SV("继续"), G.数据) && (rd(G.数据, SV("继续")) != py_dict({}))))) {
                wr(G.选块名, V(2.0)) = SV("抽奖模式");
            }
            if (((G.版本 == SV("v-1.0.0")) || (py::len(rd(G.数据, SV("拟人"))) == py::len(G.所有植物)))) {
                (void)G.选块名.append(SV("测试模式"));
            }
        }
        if ((G.name == SV("返回"))) {
            G.选块名 = V::list({SV("新游戏"), SV("设置"), SV("声明"), SV("离开")});
            if ((py::in(SV("继续"), G.数据) && (rd(G.数据, SV("继续")) != py_dict({})))) {
                G.选块名 = V::list({SV("新游戏"), SV("继续游戏"), SV("设置"), SV("声明"), SV("离开")});
            }
            if ((py::len(G.global(V("杯子"))) > V(0.0))) {
                (void)G.选块名.append(SV("花园"));
            }
        }
        return;
    }
}
