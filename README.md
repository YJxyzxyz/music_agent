# 音乐推荐 Agent（网易云 × DeepSeek × PushPlus）

每天读取网易云**推荐歌单 / 每日推荐歌曲**，结合你的**听歌习惯**挑出最契合的 5 首歌，
用 **DeepSeek** 生成一段适合发**朋友圈**的配文，再通过 **PushPlus** 推送到你的**微信**。

## 架构

```
Python Agent (src/)
  ├─ netease_crypto.py   网易云 weapi 加密（纯 Python，已用公开测试向量校验）
  ├─ netease_api.py      直连 music.163.com 的 HTTP 客户端
  ├─ login.py            Cookie 登录 + 持久化
  ├─ profile.py          从『我喜欢的音乐』构建艺人偏好画像
  ├─ selector.py         候选歌池打分，挑 5 首（兼顾多样性）
  ├─ caption.py          DeepSeek 生成朋友圈配文
  ├─ pusher.py           PushPlus 推送到微信
  ├─ orchestrator.py / scheduler.py / cli.py
```

**纯 Python，无需 Node、无需额外服务端。** 加密算法已对网易云官方社区版的常量与流程做了精确还原，
并用社区公开测试向量（`rsa("NsZytjw6GDJpdS2F")`）验证通过。

## 已验证可用的网易云接口（2026-07 实测）

| 用途 | 接口 |
| --- | --- |
| 登录态校验 | `w/nuser/account/get` |
| 推荐歌单 | `personalized/playlist`（登录后按口味） |
| 每日推荐歌曲 | `v3/discovery/recommend/songs` |
| 我喜欢的音乐 | `song/like/get` |
| 歌单详情 | `v3/playlist/detail` |
| 歌曲详情 | `v3/song/detail` |

> 注：原 `login/qr/*`（扫码登录）与 `user/record`（听歌排行）接口已被网易云下线，
> 因此本方案采用 **Cookie 登录**，并用 **likelist** 作为听歌画像数据源。

## 前置条件

1. **网易云音乐账号**（浏览器登录 music.163.com）。
2. **DeepSeek API Key**：https://platform.deepseek.com
3. **PushPlus Token**：关注公众号『PushPlus推送加』，到 https://www.pushplus.plus 获取。

## 安装

```bash
# 1. 使用已创建的 conda 环境 music_agent
conda activate music_agent

# 2. 安装依赖（已在 music_agent 环境中）
pip install -r requirements.txt
```

## 配置

```bash
cp .env.example .env
```

| 变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek Key |
| `DEEPSEEK_BASE_URL` | 默认 https://api.deepseek.com |
| `DEEPSEEK_MODEL` | 配文模型。`deepseek-v4-flash`(推荐) / `deepseek-chat` / `deepseek-reasoner`。注意 V4 系列为思考型模型，`caption.py` 已将 `max_tokens` 设为 2000 以容纳思考过程，否则 `content` 可能为空 |
| `PUSHPLUS_TOKEN` | PushPlus Token |
| `RUN_TIME` | 每日推送时间，如 09:00 |
| `N_SONGS` | 每次挑选歌曲数，默认 5 |
| `N_PLAYLISTS` | 额外抓取的推荐歌单数，默认 3 |
| `RECENT_DEDUP_DAYS` | 避免重复推荐的历史天数，默认 30，设为 0 关闭 |
| `EXPLORE_RATIO` | 新口味探索占比，默认 0.2，即每 5 首约 1 首 |
| `SCENE_MODE` | 默认配文场景：`default` / `morning` / `commute` / `focus` / `night` / `weekend` |
| `API_RETRY_ATTEMPTS` | 网易云、DeepSeek、PushPlus 请求总尝试次数，默认 3 |
| `API_RETRY_BACKOFF` | 接口重试的指数退避基数秒数，默认 1.5 |
| `API_TIMEOUT` | 外部接口单次请求超时秒数，默认 20 |

## 使用

```bash
# 1) 首次：获取并保存 Cookie
#    在浏览器登录 music.163.com → 开发者工具 → 复制 Cookie（建议整段）→ 粘贴：
python -m src.cli login

# 2) 立即跑一次（推荐 + 配文 + 推送）
python -m src.cli run

# 临时使用夜晚场景，不修改 .env
python -m src.cli run --scene night

# 推荐工作流：先生成草稿，按需重写配文，确认后再推送
python -m src.cli draft --scene night
python -m src.cli show-draft
python -m src.cli regenerate
python -m src.cli push-draft

# 3) 每天定时自动运行（后台常驻）
python -m src.cli serve

# 4) 对上一次推送的第 1 首歌点赞 / 对第 2 首点不喜欢
python -m src.cli feedback like 1
python -m src.cli feedback dislike 2

# 5) 设置艺人长期偏好，或恢复为中性
python -m src.cli artist prefer 周杰伦
python -m src.cli artist block 某艺人
python -m src.cli artist neutral 某艺人
python -m src.cli preferences
```

Cookie 保存在 `data/cookies.json`，之后自动复用；若失效运行 `login` 重新粘贴即可。

每次成功推送后，会追加 `data/history.jsonl` 推荐历史、生成
`data/journal/YYYY-MM-DD.md` 音乐日记；运行日志保存在 `data/logs/agent.log`。
选歌默认避开最近 30 天已推荐歌曲，候选不足时自动放宽限制补齐。
歌曲反馈和艺人偏好保存在 `data/preferences.json`，变更流水保存在
`data/feedback.jsonl`。不喜欢的歌曲和已屏蔽艺人会被过滤，喜欢反馈与偏爱艺人会提高后续推荐权重。

`draft` 只生成 `data/draft.json` 和 `data/draft.html`，不会发送微信消息；
`regenerate` 保留歌曲并重写配文，`push-draft` 才执行确认推送。每首歌会显示画像分、偏好分、
推荐来源和总分。探索比例会根据最近最多 20 首探索歌曲的最终反馈，每次按 5% 小幅调整，范围限制在 0% 到 50%。

## 说明与边界

- 网易云接口为社区逆向实现，请遵守相关服务条款，仅作个人使用。
- 选歌“符合听歌习惯”基于你的**『我喜欢的音乐』艺人偏好**打分，并做同艺人去重以保证歌单多样性。
- 推送到达的是 PushPlus 公众号消息，你可在微信里打开复制配文，再发到朋友圈。
- 定时运行需进程常驻（可配合系统任务计划程序 / systemd / nohup）。
- 首次运行 `run`/`serve` 会自动校验登录态，未登录会提示粘贴 Cookie。
