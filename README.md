# Werewolves Game Server

A self-hosted multiplayer social deduction game (the classic party game *Werewolves*),
built with Python (Flask) and WebSockets. One person runs the server, everyone else joins
from a browser with a game code. There is no narrator: role assignment, night actions,
accusation, the lynch vote and all death chains are driven by the engine.

- `game_engine.py` — game flow, phases, night resolution, votes, deaths, win conditions
- `roles.py` — the 24 roles, their night actions, death reactions and win conditions
- `app.py` — Flask + Socket.IO layer: lobby, admin controls, per-player state payloads
- `config.py` — defaults for timers and the default role set
- `templates/`, `static/` — the web client

## Running it

Everything runs directly on the host with a normal Python 3 installation. There is no
Docker, no container and no external service involved.

```
pip install -r requirements.txt
python app.py            # serves the game on http://127.0.0.1:5000
```

The interactive web client needs the dependencies above (Flask, Flask-SocketIO, ...).
The game engine itself (`game_engine.py`, `roles.py`, `config.py`) only uses the Python
standard library, so engine-level checks run offline in a second or two:

```
python -m pytest -q
```

## 行为规格（验收标准）

下面是本项目的验收标准。每条都是可测试的客观条款，改动请以这里的条款为准，
不要以「已知问题」为准。「已知问题」只是部分现象，不是完整清单。

**1. 角色分配 `Game.assign_roles(selected_role_keys)`**

1.1 被选中的角色集合里包含 `Seer` 时，本局必须分配到且只分配到一名 Seer；
`Villager` / `Werewolf` 继续按人数公式自动补足，不需要在列表里额外指定。

1.2 任何一局都至少有一名狼人阵营玩家（`Werewolf` 或特殊狼人）。当被选中的特殊角色
数量超过玩家人数时，宁可丢弃多余的特殊角色，也不能把狼人名额挤掉。

1.3 狼人数量与玩家人数的对应关系保持不变：4–6 人 → 1 只，7–8 人 → 2 只，
9–11 人 → 3 只，12–16 人 → 4 只，其余按玩家人数的 25% 向下取整且至少 1 只。

1.4 每个玩家恰好拿到一个角色实例，不留空、不重复持有同一个实例。

**2. 夜间结算 `Game.resolve_night_deaths()`**

2.1 狼人击杀判定：活跃狼人少于 5 人时要求所有狼人投同一目标；活跃狼人达到 5 人及以上时，
要求投同一目标的票数达到活跃狼人人数的 80%。弃权（`"Nobody"`）既不算同意也不算反对，
但必须计入分母——少数狼人投票、其余狼人弃权时不得造成死亡。

2.2 被守护（`protected`）、被女巫救治（`healed`）或为 Monster（`immune_to_wolf`）的目标
不会被狼人咬死。

**3. 放逐投票 `Game.resolve_lynch_vote()`**

3.1 放逐成立的条件是「活着的玩家中投 yes 的人数超过活着的玩家人数的一半」。

3.2 死者的票（Ghost 票）只出现在结果摘要里（名字显示为 `Ghost`），不参与放逐是否成立的判定：
死者的 yes 票不能补足活人的票数，也不能改变判定结果。

**4. 市长继承 `Mayor.on_death()`**

4.1 只有当被指定的继承人属于 `GOOD_MAYORS` 时才发生继承；继承后该玩家的角色实例获得
市长能力（夜间可以指定下一任继承人，`is_night_active` 为真，`next_mayor_id` 为 `"not_set_yet"`）。

4.2 继承人不属于 `GOOD_MAYORS` 时不得发生继承，也不得广播「新市长上任」之类的消息。

**5. 丘比特 `Cupid.night_action()`**

5.1 丘比特的能力只能用一次（第一晚）。必须选择两名不同的、且都不等于自己的玩家。

5.2 选择无效时（选中自己、两人相同、缺少第二位目标）不得消耗这次能力，也不得建立恋人关系：
之后的一晚仍然可以正常使用。

5.3 成功建立恋人关系后消耗能力，此后按普通村民参与夜间投票。

**6. 胜负判定 `Game.check_game_over()`**

6.1 村民阵营获胜的前提是场上至少还有一名活着的村民阵营玩家（`role.team == "Villagers"`）。

6.2 场上没有活着的村民阵营玩家时，不得判村民阵营获胜；这种局面只能由独狼/中立角色
自身的获胜条件或狼人条件决定，都不满足时游戏不结束。

6.3 狼人阵营的条件保持不变：活着的狼人数量 ≥ 其他活着玩家数量时狼人获胜。

**7. 回归约束**

7.1 `tests/` 下的既有用例是回归基线，必须保持全绿。

7.2 不允许削弱、删除或跳过既有断言来「让测试通过」；新增的测试必须在修复前失败、修复后通过。

## 已知问题（不完整清单，不是验收标准）

- 有人反馈：管理员明明勾了预言家，整局下来没有一个人能验人。
- 有人反馈：人多的时候狼人还没商量好，猎物就已经死了。
- 有人反馈：放逐投票明明只有一票同意，人却被吊死了。
- 有人反馈：系统广播了「新市长上任」，可那位新市长根本没有市长的权力。

以上只是玩家能看到的一部分现象。请以「行为规格（验收标准）」为准，自己把条款对应的
问题找全；只修上面这几条不算完成。

## Setup notes

- `FLASK_SECRET_KEY` and CORS origins live in `.env.werewolves`.
- Persistent sessions: a player may refresh the browser mid-game and keep their seat
  (the countdown may be off until the next phase change).
- No network calls and no extra services are needed by the engine or its tests.
