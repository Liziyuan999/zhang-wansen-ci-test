---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f92a25702084128d164d6c111d7f7222_fc4dca71e89911f1b0c5525400cd780f
    ReservedCode1: u2uFZOzOwGp6TsUC/m+Jbo3Z2W2TwA3GT+NI0FIQvoLAMzfF/HOpPB1yzt9YnopkMTq15V9DpP/PWDhjjQbJAzqk6Ua6QIyKvuL1O/ozpsCWGVDXDSv7I19SiDQxIxTH9ZP3E1+Vl9chv6FABfXtqpCQYPxTbD8HSstgWpig98rR0R2LbtGFzVDM10Q=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f92a25702084128d164d6c111d7f7222_fc4dca71e89911f1b0c5525400cd780f
    ReservedCode2: u2uFZOzOwGp6TsUC/m+Jbo3Z2W2TwA3GT+NI0FIQvoLAMzfF/HOpPB1yzt9YnopkMTq15V9DpP/PWDhjjQbJAzqk6Ua6QIyKvuL1O/ozpsCWGVDXDSv7I19SiDQxIxTH9ZP3E1+Vl9chv6FABfXtqpCQYPxTbD8HSstgWpig98rR0R2LbtGFzVDM10Q=
---

# CI/CD 测试门禁与手动发版演练

> 适用版本：2026-11-25 起  
> 前置事实：CD（Gitee Webhook → 自建轻量流水线 → ECS 自动上线）早已在跑；本次补齐的是 **CI 测试门禁**。  
> 一句话结论：**从今天起，单元测试不过，镜像就构建不出来，线上不会变。**

---

## 一、现在是什么形态

| 环节 | 位置 | 触发方式 | 失败后果 |
|---|---|---|---|
| 提交 | 本地 git | 你手动 `git push` | 无 |
| 通知 | Gitee Webhook `http://47.95.34.112:8080/webhook` | push 自动 | Gitee 侧 200，不代表部署成功 |
| 拉取+构建+测试 | ECS `/root/ci/deploy.sh` | Webhook 后台异步 | **构建失败即整条中止，旧容器继续对外服务** |
| 上线 | `docker compose up -d` | 构建成功后 | 健康检查 30×3s 失败则自动回滚 `:bak-$TS` |
| 验证 | `:8080/health` + `/api/health` + 页面 | 部署脚本自带 | 失败回滚并 `exit 2` |

关键点：**测试门禁不在 Gitee，也不在 Jenkins，而是内建在 `server/Dockerfile` 的镜像构建里。**  
这意味着任何一次 `docker compose build backend` 都必须先跑通单元测试，绕不过去。

---

## 二、本次改动清单

| 文件 | 类型 | 作用 |
|---|---|---|
| `server/tests/test_unit_core.py` | 新增 | 33 个单元测试，覆盖密码哈希、JWT 双 token、TOTP、统一响应、错误码 |
| `server/tests/conftest.py` | 新增 | 把 4 个脚本式验证件排除出 pytest 收集，避免 `SystemExit` 崩测试会话 |
| `server/Dockerfile` | 修改 | 由两阶段扩成三阶段：`builder` → **`tester`（跑 pytest）** → `runtime`（继承 tester） |
| `server/requirements.txt` | 修改 | 追加 `pytest`、`coverage`（运行时不用，仅供门禁） |
| `server/.dockerignore` | 新增 | 构建上下文瘦身，剔掉 534MB 的 `.venv` 和本地 db/chroma/uploads |
| `server/tests/test_smoke.py` | 修改 | 修掉写死「15 张表」的死断言（实际 34 张），改为「核心表齐全且不少于 15 张」 |
| `deploy/ci-gate.sh` | 新增 | 本地/服务器预检脚本，不构建镜像就能判断这次改动能不能上线 |

### Dockerfile 三阶段原理

```
builder（装依赖）
   ↓ 复制 site-packages 与 bin
tester（COPY 源码 → RUN pytest）
   ↓ pytest 失败 = 这一层失败 = 镜像不存在 = 无法 up -d
runtime（FROM tester，只有测试通过才有这个镜像）
```

`runtime` 直接继承 `tester`，所以**测试不通过时根本产不出可运行镜像**，这不是靠脚本判断，是构建机制本身保证的。

### 死断言为什么要改

原断言是集合全等：

```python
expected = {...15 张表名...}
check("15张ORM表已注册", set(Base.metadata.tables.keys()) == expected)
```

数据库迭代到 34 张表后这条必然红。一旦把它接进门禁，**每一次部署都会被自己拦死**。  
改为「核心 15 张一张都不能少，且总数 ≥ 15」，新增表不再误伤。

---

## 三、手动演练：自己把整条链路走一遍

以下命令按顺序复制执行即可。  
本地工作目录：`E:\AI-Agent知识库`

### 步骤 0　先看能不能过门禁（不构建镜像）

```powershell
cd E:\AI-Agent知识库
```

后端（本机若无 venv，可跳到服务器上跑，或先 `pip install pytest fastapi pydantic-settings bcrypt PyJWT`）：

```powershell
cd server
python -m pytest tests/ -q
```

期望输出：

```
.................................                    [100%]
33 passed in 2.4s
```

前端：

```powershell
cd E:\AI-Agent知识库\web
npm run build
```

期望 `built in xx s` 且退出码 0。

> 也可以用脚本一次跑完（Git Bash 或服务器上）：
> ```bash
> bash deploy/ci-gate.sh          # 全部
> bash deploy/ci-gate.sh backend  # 只后端
> ```

---

### 步骤 1　故意让门禁变红，亲眼看它拦你

打开 `server/tests/test_unit_core.py`，找到：

```python
    def test_access_token_roundtrip(self):
        payload = decode_token(create_access_token(42))
        assert payload is not None
        assert payload["sub"] == "42"
```

把 `"42"` 改成 `"999"`，保存，然后：

```powershell
cd E:\AI-Agent知识库\server
python -m pytest tests/ -q
```

期望：

```
1 failed, 32 passed
```

**退出码 1。** 这就是门禁的"红"。

> 想更直观地看它如何阻断构建，可执行（服务器上）：
> ```bash
> cd /root/project && docker compose build backend; echo "构建退出码=$?"
> ```
> 你会看到 pytest 失败后 `build` 直接中断，退出码非 0，**没有任何新镜像产出**。

---

### 步骤 2　还原，确认变绿

把 `"999"` 改回 `"42"`：

```powershell
cd E:\AI-Agent知识库\server
python -m pytest tests/ -q
```

期望重新变回 `33 passed`、退出码 0。

---

### 步骤 3　提交并推送（这一步才会真正上线）

```powershell
cd E:\AI-Agent知识库
& "C:\Program Files\Git\cmd\git.exe" add server/ deploy/
& "C:\Program Files\Git\cmd\git.exe" commit -m "ci: 后端单元测试门禁内建于镜像构建（pytest in Dockerfile tester stage）"
& "C:\Program Files\Git\cmd\git.exe" push origin main
```

> 本机 git 不在 PATH，所以用全路径。若已配好 alias 可直接 `git push origin main`。  
> 注意本地 `main` 没有 upstream，必须写 `git push origin main`，不能只写 `git push`。

push 成功后 **5 秒内**，Gitee 就会把事件打到 Webhook，服务器开始在后台构建。

---

### 步骤 4　登服务器看部署日志（真正的成败在这里）

```powershell
ssh root@47.95.34.112
```

```bash
tail -f /root/ci/deploy.log
```

你要在这份日志里**亲眼看到 pytest 那一段**：

```
============ [1/6] 拉取代码 ============
============ [2/6] 构建镜像 ============
...
tests/test_unit_core.py ......................... [100%]
33 passed in 2.4s
...
============ [3/6] 备份当前镜像 ============
============ [4/6] 启动新容器 ============
============ [5/6] 健康检查 ============
============ [6/6] 部署成功 ============
```

- 若出现 `33 passed` → 门禁放行，继续走部署六阶段；
- 若出现 `1 failed` 或 `ERROR` → **构建中止，deploy.log 会停在 2/6，线上容器完全没有变化**，这是预期行为。

查看是否真的产出了新镜像：

```bash
docker images | grep knowseek
docker ps --filter name=knowseek-backend --format "{{.Names}}\t{{.Status}}\t{{.Image}}"
```

---

### 步骤 5　验证线上

浏览器打开 `http://47.95.34.112`，**必须 `Ctrl + F5` 硬刷新**（或开无痕窗口）。
普通 F5 会命中旧 JS 缓存，让你误判为"部署没生效"。

服务端自查（在服务器上跑）：

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8080/health
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
```

期望：`{"code":0,...}`、`{"status":"ok","service":"knowseek-ci"}`、`200`。

---

### 步骤 6　演练"门禁把坏代码拦在生产之外"

这是整套流程里最有价值的一次验证，建议一定做一次：

1. 把步骤 1 的失败断言（`"42"` → `"999"`）**保留不改**；
2. `git commit` 并 `git push origin main`；
3. `ssh root@47.95.34.112` 后 `tail -f /root/ci/deploy.log`；
4. 你会看到构建在 pytest 处失败，`deploy.sh` 中止，**线上页面照常访问、版本没变**；
5. 本地改回 `"42"`，再 push 一次，恢复正常。

做完这一步，你就真正拥有了"提交即验证"的能力，而不是"提交即上线"。

---

## 四、服务器侧一次性确认（建议做一次）

登服务器后逐条确认：

```bash
# 1. 部署脚本是否遇错即停（决定门禁失败时会不会继续往下部署）
grep -n "set -e" /root/ci/deploy.sh

# 2. 构建命令是不是走 compose build（只有这样才会执行 Dockerfile 的 tester 阶段）
grep -n "compose build\|docker build" /root/ci/deploy.sh

# 3. 备份与回滚标签机制是否在
grep -n "bak-\|last_good" /root/ci/deploy.sh

# 4. Webhook 服务是否活着
systemctl status knowseek-ci --no-pager -l | head -20
curl -s http://127.0.0.1:8080/health
```

若第 1 条查不到 `set -e`，需要在部署脚本开头补上，否则 pytest 失败后脚本可能继续执行 `up -d`：

```bash
set -euo pipefail
```

改完重启服务：

```bash
systemctl restart knowseek-ci
```

---

## 五、耗时预期（2 核 3.6G / 前后端不并行构建）

| 改动类型 | 预计耗时 |
|---|---|
| 只改前端，依赖未变 | 1.5 – 3 分钟 |
| 只改后端代码，依赖未变 | 2 – 4 分钟（含 pytest 约 3 秒） |
| 改了 `requirements.txt` | 5 – 10 分钟（重装依赖层） |
| 首次构建（无缓存） | 10 – 20 分钟 |

门禁本身的开销只有 2–3 秒，可以忽略。

---

## 六、常见问题

**Q1：`docker compose build` 时提示找不到 pytest**
`server/requirements.txt` 里的 `pytest` 没进去，或服务器在用旧依赖缓存。执行 `docker compose build --no-cache backend`。

**Q2：构建报 "no tests ran"，退出码 5**
`server/.dockerignore` 误排除了 `tests/`。它必须保留，否则 pytest 收集 0 个用例也视为失败（这是刻意设计的 fail-closed）。

**Q3：本地 `pytest tests/` 报 `INTERNALERROR: SystemExit`**
`server/tests/conftest.py` 被删了或没生效。它负责排除 `test_admin.py` 等脚本式文件——那些文件模块级就执行、结尾 `sys.exit()`，pytest 一收集就崩。

**Q4：push 后 Gitee 显示 200，但线上没变**
Gitee 的 200 只代表 Webhook 请求送达，与部署成败无关。必须看 `/root/ci/deploy.log`。

**Q5：页面看着没更新**
`Ctrl + F5` 硬刷新，或直接访问 `http://47.95.34.112/?v=2` 绕过缓存。

**Q6：想回滚到上一版**
```bash
cd /root/project
docker images | grep knowseek-backend     # 找到 :bak-<时间戳>
docker tag knowseek-backend:bak-20261125-1430 knowseek-backend:latest
docker compose up -d --no-deps backend
```

---

## 七、面试口径（如需对外表述）

> 「CD 链路是我自建的轻量流水线：Gitee Webhook 触发，纯标准库实现约 15MB，systemd 托管，token 校验，5 秒内先返 200 再异步部署，避免 Gitee 判超时；部署分六阶段，`up -d` 前给镜像打 `:bak-时间戳` 标签并记录 `.last_good`，健康检查 30 次×3 秒失败就自动回滚。  
> CI 侧我把单元测试门禁直接内建进镜像构建：Dockerfile 拆成 builder / tester / runtime 三阶段，runtime 继承 tester，**测试不过就产不出镜像**，从构建机制上保证坏代码上不了线，而不是依赖脚本判断。测试覆盖密码哈希、JWT 双 token、TOTP、统一响应与错误码，33 个用例约 2.5 秒。」

不可说"用 Gitee 的 CI/CD"——Gitee 在这条链路里只负责事件通知。
*（内容由AI生成，仅供参考）*
