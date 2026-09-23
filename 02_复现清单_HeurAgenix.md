# HeurAgenix 完全复现清单（执行版）

> 配套阅读报告：`01_文献阅读报告_HeurAgenix.md`  
> 事实与参数核对文件：`evidence/paper_facts.json`  
> 目标论文：arXiv:2506.15196v2；代码：microsoft/HeurAgenix  
> 服务器：`202.121.181.105`，端口候选 `223–234`，用户 `shiliangliang`，端口内有多张 GPU，需自动选择空闲卡。  
> **执行原则：先复现“无 API 依赖的核心链路”（A 档），再按用户决策决定是否跑依赖 GPT-4o 的演化与 LLM 在线选择（B 档），最后按需补外部 baseline（C 档）。**

---

## 0. 复现目标分级与验收定义

| 档位 | 内容 | 是否依赖外部 LLM API | 本次优先级 |
|---|---|---|---|
| **A1 确定性复现** | 用论文快照的 seed/evolved heuristics 复现 Table 5、Figure 7 的确定性 gap | 否 | P0 |
| **A2 数据管线复现** | 重建离线训练数据收集与 JSON 构造管线（论文未公开的部分） | 否 | P0 |
| **A3 训练复现** | Qwen2.5-7B-Instruct-1M + LoRA + GRPO + POR/CPR，复现 Table 4 | 否（训练本身） | P0 |
| **A4 微调选择器评测** | 复现 Table 3、Figure 9 的 TSPLIB 评测 | 否（推理本地） | P0 |
| **B1 LLM 在线选择** | GPT-4o/替代模型复现 Table 6、Figure 8（含 TTS） | 是 | P1（视 API 决策） |
| **B2 启发式演化** | 用 GPT-4o/替代模型重跑 Algorithm 1，复现 Figure 7/Table 5 的“演化过程” | 是 | P1（视 API 决策） |
| **C 外部 baseline** | GLS/ACO/OR-Tools/EoH/ReEvo 等 | 部分 | P2（可选） |

**统一验收口径：**
- 每个 instance 的 gap `= (v - v_u)/v_u × 100%`，`v_u` 使用论文时期 `analysis.py` 的 upper_bound 列表（见下）。
- 求解类实验每个实例至少跑 3 次；确定性启发式可只跑 1 次并注明方差为 0。
- 与论文对比时同时给出：均值、标准差、论文值、差值、代码/模型版本、日期。
- 所有产物进入 `results/`，每个结果带 `meta.json`（commit、pool、model、参数、seed、时间）。

---

## 1. 阶段 0：本地冻结与事实核对（不登录服务器）

### 0.1 代码版本冻结
- [ ] clone 官方仓库并 fetch 完整历史：
  ```bash
  git clone https://github.com/microsoft/HeurAgenix.git
  cd HeurAgenix
  git fetch --unshallow origin
  ```
- [ ] 创建三份工作区：
  - `core_paper/` ← checkout `f9ec60f`（2025-06-26，论文核心实验用；evolved heuristics 与 `de8a9cf` 完全一致）
  - `core_paper_alt/` ← checkout `de8a9cf`（2025-06-24，arXiv v2 当天快照）
  - `training_recovered/` ← 从 `6e4fc66`（2025-06-06）提取微调代码：
    ```bash
    mkdir -p training_recovered
    for f in src/training src/pipeline/heuristic_selection_data_collector.py \
             collect_heuristic_selection_data.py src/util/compare_heuristics.py \
             src/problems/tsp/evaluation_function.py; do
      git archive 6e4fc66 "$f" | tar -x -C training_recovered/
    done
    ```
- [ ] 记录 commit hash、日期、tree hash 到 `evidence/code_freeze.json`。
- [ ] 记录论文时期 `analysis.py` 的 upper_bound 列表：
  从 `8251fbe^:analysis.py` 提取（`8251fbe` 是删除 training/analysis 的 “update readme” commit）。
- [ ] 确认所有 evolved heuristics 的 SHA1 与 `f9ec60f` 一致；不要使用当前 `main` 的这些文件。

### 0.2 数据冻结
- [ ] 下载 HF 数据集固定 revision：
  ```bash
  python3 -c "from huggingface_hub import snapshot_download; \
  snapshot_download('VictorYXL/HeurAgenixDataset', repo_type='dataset', \
  revision='6008adba8895821ad09b8a649ef2e74be67f725a', local_dir='raw_data')"
  ```
  数据约 **27 MB / 445 files**。
- [ ] 核对每个 problem 的 raw 文件列表，标记哪些是论文使用的、哪些是数据集多送的（TSP `pa561.ts225`；CVRP Golden/Loggi/ORTEC；JSSP LA31–40；MKP PB/SENTO/mknapcb9；MaxCut g21+ 等）。
- [ ] 生成 `evidence/paper_splits.json`（精确 split + 参考值，`paper_facts.json` 里已有初版）。

### 0.3 运行环境盘点（本地）
- [ ] 本地已有：`git`、`ssh`、`sshpass`、`rsync`、`pdftotext`、Python3。
- [ ] 确认本地下载/中转能力；如果服务器外网受限，需要本地下载后 rsync。

---

## 2. 阶段 1：服务器预检与选卡（只读侦察，不训练）

> 端口 223–234 中部分可能不可用/无卡空闲；逐个探测，选 **空闲显存最大、利用率最低** 的卡。优先顺序：A100 80G / A6000 48G / A6000 24G / 4090 24G。

### 2.1 自动探测脚本（本地执行，只读）
```bash
# 变量
HOST=202.121.181.105
USER=shiliangliang
PASS='请在此处使用用户提供的密码'
OUT=evidence/server_scan_$(date +%Y%m%d_%H%M%S).txt

for PORT in $(seq 223 234); do
  echo "===== PORT $PORT =====" | tee -a "$OUT"
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=6 -p "$PORT" \
    "$USER@$HOST" '
      echo "HOST=$(hostname)"; 
      echo "--- GPU ---";
      nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu \
        --format=csv,noheader 2>/dev/null || echo "no nvidia-smi";
      echo "--- DISK ---";
      df -h / /home /Data /data 2>/dev/null | sort -u;
      echo "--- CPU/MEM ---";
      nproc; free -g;
      echo "--- CUDA ---";
      nvcc --version 2>/dev/null | tail -1;
      nvidia-smi | tail -3;
    ' 2>&1 | tee -a "$OUT"
done
```

### 2.2 选卡规则
- [ ] 必须满足：GPU 显存空闲 ≥ 40GB（首选）；若只有 24GB，先以 QLoRA 方案评估，优先再找 48GB 卡。
- [ ] GPU 计算利用率 < 20%，且没有其他用户进程（`nvidia-smi` 可见 PID，尽量避开）。
- [ ] 宿主盘剩余 ≥ 150GB（含 model + checkpoint + vLLM cache + 数据/结果）；若 home 配额小，改到 `/Data/<user>` 或大容量挂载点。
- [ ] 记录 `PORT`、`GPU_INDEX`、`日 期`、宿主机名、SSH 可用性到 `evidence/server_choice.json`。
- [ ] 选择 1 张主卡训练；如允许多端口并行，再选 1–2 张卡分别跑 vanilla GRPO / raw eval / 评测。

### 2.3 创建项目目录
```bash
sshpass -p "$PASS" ssh -p "$PORT" "$USER@$HOST" \
  'mkdir -p ~/heura_repro/{repo,data,output,results,models,envs,logs}'
```
- [ ] 检查 `~` 所在磁盘配额；若不足，使用 `/Data/<user>/heura_repro`。

---

## 3. 阶段 2：服务器环境与依赖

### 3.1 基础工具
- [ ] `git`, `git-lfs`, `build-essential`, `cmake`, `ninja`, `tmux`, `htop`, `nvtop`, `rsync`, `wget`, `curl`, `jq`。
- [ ] 若服务器无外网：本地下载 model/data/whl 后 rsync；pip 使用内网/清华镜像。
- [ ] HuggingFace 访问测试：`HF_ENDPOINT=https://hf-mirror.com huggingface-cli download ...`；不行则 ModelScope。

### 3.2 代码部署
- [ ] 上传/拉取冻结代码到 `~/heura_repro/repo/HeurAgenix_paper/`（f9ec60f）、`~/heura_repro/repo/HeurAgenix_training/`（6e4fc66 提取件）。
- [ ] 上传 curated data 到 `~/heura_repro/output/<problem>/data/...`（各 problem 下 `train_data/validation_data/test_data/smoke_data`）。
- [ ] 上传 `paper_facts.json`、`paper_splits/`、heuristic pool 清单。

### 3.3 Python 环境（两套，隔离）
**Env-A（核心实验 / 数据收集）：**
- [ ] 按 `core_paper f9ec60f:environment.yml` 创建 `heura-core` 环境（Python 3.10 + torch + networkx + tsplib95 + pandas + dill + openai 等）。
- [ ] 验证 `python launch_hyper_heuristic.py -h`、`tsplib95.load` 正常。

**Env-B（GRPO 训练 / vLLM 推理）：**
- [ ] 优先按 recovered `6e4fc66` 时代版本锁定：
  - Python 3.10/3.12
  - `torch==2.5.1` (+cu124)
  - `vllm==0.7.3`
  - `transformers==4.49.0`
  - `accelerate==1.4.0`
  - `peft==0.12.0`
  - `bitsandbytes==0.45.3`
  - `unsloth` + `unsloth_zoo==2025.2.7`（或按 CUDA 对应版本）
  - `trl`（2025 年初支持 GRPOTrainer + vLLM 的版本）
  - `datasets`, `langdetect`, `spacy==3.8.5`, `en_core_web_md`, `wandb`
- [ ] 若固定旧版失败（新卡/CUDA 不兼容），第二方案：移植到当前 TRL `GRPOTrainer` + PEFT + vLLM，在 `notes/` 记录移植差异。
- [ ] `python -c "import torch,vllm,transformers,trl,peft,unsloth; print(...)"` 一次性通过。
- [ ] `python -m spacy download en_core_web_md`。
- [ ] 单卡 48GB 下做 1 步 mini smoke training（见 7.1）。

### 3.4 模型下载
- [ ] Qwen2.5-7B-Instruct-1M（15.24 GB，非 gated）：
  ```bash
  export HF_ENDPOINT=https://hf-mirror.com
  huggingface-cli download Qwen/Qwen2.5-7B-Instruct-1M \
    --local-dir ~/heura_repro/models/Qwen2.5-7B-Instruct-1M --local-dir-use-symlinks False
  ```
- [ ] 校验 4 个 safetensors 总大小、README config、tokenizer。
- [ ] Fallback：`Qwen/Qwen2.5-7B-Instruct`（标准版）或 Qwen2.5-7B-Instruct-1M 的 ModelScope 版本；在 `meta.json` 记录。
- [ ] 单卡 24GB 候选：加载 4bit QLoRA + 小 `max_seq_length` 先做 dry-run；必要时申请 48GB 卡。

### 3.5 磁盘验收
- [ ] 模型下载后剩余空间 ≥ 100GB 才允许开始训练。
- [ ] `save_steps` 调大（例如 500）或只保存最终 LoRA，防止 checkpoint 爆炸。
- [ ] 训练前/后都跑 `df -h`，记录到 `logs/disk_<stage>.txt`。

---

## 4. 阶段 3：数据 curation（复现 split 和 pool）

### 4.1 生成精确 split
- [ ] 写 `scripts/prepare_paper_splits.py`，按论文 Appendix E + Table 5 的 exact 列表从 raw_data 复制/硬链接到：
  ```
  output/<problem>/data/train_data/
  output/<problem>/data/validation_data/
  output/<problem>/data/test_data/
  output/<problem>/data/smoke_data/
  ```
- [ ] **TSP**
  - train: `train_case_0..19.tsp` (20)
  - validation: `brg180, eil101, gr202, pr124, pr152, rd100, u159` (7)
  - test: `kroA100, kroA150, kroB100, kroB200, kroC100, bier127, tsp225, a280, pcb442, gr666, pr1002, pr2392` (12)
- [ ] **CVRP**
  - train: `train_case_1..20.vrp`
  - validation: `A-n63-k10, B-n67-k10, E-n76-k10, F-n45-k4, M-n101-k10, P-n70-k10, X-n101-k25`
  - test: `A-n80-k10, B-n78-k10, E-n101-k14, F-n135-k7, M-n200-k17, P-n101-k4`
- [ ] **MKP**
  - train: `train_case_1..20.mkp`
  - validation: `mknap1_1..7.mkp`
  - test: `mknapcb1_1..5.mkp`, `mknapcb4_1..5.mkp`
- [ ] **JSSP**
  - train: `train_case_1..20.jssp`
  - validation: `LA21..LA30.jssp`
  - test: `LA01..LA20.jssp`
- [ ] **MaxCut**
  - train: `train_case_1..20.mc`
  - validation: 从 raw `test_data/g11.mc .. g20.mc` 取（build 时复制过来）
  - test: `g1..g10.mc`（显式从 raw `test_data/` 取，避免和 validation `g1.mc` 歧义）
- [ ] 生成 `paper_splits_manifest.json`：每个文件的原路径、目标路径、MD5、参考值。
- [ ] 运行一次 `Env(data_name=...)` smoke test 验证所有文件都能 load；特别检查 TSP `tsp225` 不是 `ts225`。

### 4.2 构建 known upper_bound 表
- [ ] 按 `analysis.py` 的 `total_experiments` 构建 `reference_values.json`：
  - TSP test：`[21282,26524,22141,29437,20749,118282,3919,2579,50788,294358,259045,378032]`
  - CVRP test：`[1762,1221,1067,1162,1275,681]`
  - MKP test：`[24381,24274,23551,23534,23991,23064,22801,22131,22772,22571]`
  - JSSP test：`[666,655,597,590,593,926,890,863,951,958,1222,1039,1150,1292,1207,945,784,848,842,902]`
  - MaxCut test：`[11624,11620,11622,11646,11631,2178,2006,2006,2054,2000]`
- [ ] 用脚本验证：所有 test 文件名与参考值一一对应，数量正确。
- [ ] 注明：`tsp225=3919` 是按论文仓库口径，不是重新查 TSPLIB；CVRP/MKP 同理。

### 4.3 构建 heuristic pool（三套候选）
- [ ] **P1 = evolved only**：每个问题的 `evolved_heuristics/` 3 个文件（对应论文 3 个 seed 的演化结果）。
- [ ] **P2 = Appendix E deterministic basics + 3 evolved**（推荐主口径）：
  - TSP: 10 basic + 3 evolved = 13；
  - CVRP: 9 + 3 = 12；
  - MKP: 12 + 3 = 15；
  - JSSP: 10 + 3 = 13；
  - MaxCut: 8 + 3 = 11。
- [ ] **P3 = released `heuristic_type=evolved` 合并逻辑**：basic 全量 + evolved，剔除“基名相同”的 basic（TSP 14 + 3 去重后 14；其他类似）。
- [ ] 每套 pool 建一个目录，生成 `pool_manifest.json`（name, file, sha1, category: exploration/refinement, deterministic/random）。
- [ ] 对 pool 中每个 heuristic 跑 smoke_data，确保能产生合法算子；记录失败/空算子的 heuristic。

---

## 5. 阶段 A1：确定性复现 Table 5 / Figure 7（无 LLM）

### 5.1 目标
- [ ] 对 Table 5 的每一对 seed/evolved，逐一在 test split 上运行单启发式。
- [ ] TSP 需要 3 对：cheapest_insertion、farthest_insertion、nearest_neighbor；CVRP 3 对；MKP 3 对；JSSP 3 对；MaxCut 3 对。
- [ ] 论文 Table 5 表格和平均值（供验收）：
  - TSP nearest neighbor：24.59 → 9.06
  - CVRP nearest neighbor：48.80 → 36.55
  - MKP greedy by density：8.03 → 2.69
  - JSSP SPT first：180.47 → 23.30
  - MaxCut balanced cut：60.41 → 6.45
  - 完整每实例数字见 `01_文献阅读报告_HeurAgenix.md` 与论文 Table 5。

### 5.2 运行
- [ ] 写批量脚本 `scripts/run_table5_single.py`：
  ```bash
  python launch_hyper_heuristic.py -p tsp -e nearest_neighbor_e8a4 \
      -d output/tsp/heuristics/evolved_heuristics -t kroA100.tsp \
      -r table5/tsp_nn_evolved
  ```
  （旧版 CLI 的 `-t` 可能只接受单个 name；建议直接调 `SingleHyperHeuristic` 或写 Python 驱动，避免目录歧义。）
- [ ] 每个问题、每个 heuristic、每个 test instance 运行；
- [ ] 结果统一写 `results/table5_raw.csv`：`problem, instance, heuristic_file, key_item, value, reference, gap, runtime, commit, pool`。
- [ ] 确定性 heuristic 跑 1 次；stochastic heuristic 如需列入则 3 次，但 Table 5 声称全确定性，优先用确定性版本。

### 5.3 验收
- [ ] 每个问题 average gap 与论文差值 ≤ 0.5 个百分点（理想为 0）；
- [ ] 若有差异：先确认 heuristic 文件版本（f9ec60f vs main）→ 再确认 reference 值 → 再确认 heuristic pool / 执行步数。
- [ ] 输出 `results/table5_gap.csv`、`figures/fig7_repro.pdf`（bar chart 复刻 Figure 7）。
- [ ] 预计耗时：2–6 CPU 小时；可多进程。

### 5.4 代码 walkthrough（写进文档）
- [ ] 记录 `SingleHyperHeuristic` 的终止条件、每步 `env.run_heuristic`、`construction_steps` 定义；
- [ ] 记录 CVRP/MKP/JSSP/MaxCut 的 `key_item` 和 gap 公式差异。

---

## 6. 阶段 A2：离线训练数据收集与 JSON 构建

> 论文未公开训练数据。这是复现中“必须自己重建”的部分。原则：以 released 代码的字段格式为准，先做小规模 pilot，验证后再放大。

### 6.1 收集器准备
- [ ] 从 `6e4fc66` 取 `collect_heuristic_selection_data.py`、`src/pipeline/heuristic_selection_data_collector.py`、`src/util/compare_heuristics.py`、`src/problems/tsp/env.py|components.py|evaluation_function.py`、prompt 文件。
- [ ] 把 `Env`/`load_heuristic` 的路径接口对齐到我们的 frozen TSP 代码（可能需小 patch）。
- [ ] 确定 pool：先用 **P2**；同时准备 P1/P3 以便 pool 校准。
- [ ] 确定 `search_time`：
  - 论文没有明确给出离线数据收集的 T；代码默认 `1000`。
  - 先跑 `-s 100` pilot 检查数据质量和耗时；
  - 若资源允许，再跑 `-s 1000` 作为主数据；两版都记录，用 `search_time` 标注。
- [ ] 随机种子：收集器内部用 `random`，需固定 `PYTHONHASHSEED`、`random.seed`（可能需要 patch），保证 greedy 轨迹可复现；stochastic 轨迹用不同 seed 多次跑以覆盖多样性。

### 6.2 每个 train case 生成 greedy + stochastic 轨迹
```bash
# 示意；实际以脚本包装为准
python collect_heuristic_selection_data.py -p tsp \
  -c output/tsp/data/train_data/train_case_0.tsp \
  -d evolved -s 100 -m best -b \
  -fd train_case_0_best_s100

python collect_heuristic_selection_data.py -p tsp \
  -c output/tsp/data/train_data/train_case_0.tsp \
  -d evolved -s 100 -m random -b \
  -fd train_case_0_random_s100
```
- [ ] 对 `train_case_0..19` 都跑 best 和 random 两种模式；
- [ ] 每个模式建议 2–3 个不同随机种子，得到更多状态覆盖；
- [ ] 输出目录保留 `round_*.txt`、`information.txt`、日志；
- [ ] 记录每个 round 的 `heuristic_name -> [terminal values] -> score`。

### 6.3 构建 GRPO 训练集
- [ ] 写 `scripts/build_grpo_dataset.py`，从 `round_*.txt` 解析：
  - 状态：`previous_solution` + global features + state features（按 old `evaluation_function.py` 的 TSP 版本）；
  - 每个 heuristic 的 `average_score` / 原始 results；
  - `selected_heuristics`（best 模式=argmax；random 模式=random，仅作状态多样性；label 仍由 score 决定）。
- [ ] 生成论文/代码需要的 reward dict 字段：
  - `correct_answer`：当前状态 Q 分数最高的启发式；
  - `positive_samples`：按 Q 降序取 top 一部分（论文 Figure 5 用 top 30%；建议同时生成 30%/50% 两个版本做消融）；
  - `negative_samples`：按 Q 升序的 bottom 一部分（建议与正集不重叠；需要消融 `n_pos/n_neg`）；
  - `error_samples`（如果实现论文 Eq.2）：正负集之外的“错误区”，当前 released 代码没有该字段，需要在自定义 reward 中实现；
  - `illegal` / `disabled_algorithms`：对当前状态无法产生合法操作、或 rollout 全部失败的启发式；
  - `card_problem`：`["tsp"]`（多问题混合时才可能出现 cvrp）；
  - `card_state`：空解 → `unvisited`；部分 → `partially visited`；完整 → `fully visited`；
  - `card_alg_type`：correct_answer 所属类别（refinement / exploration）；
  - `card_cost`：`None`（访问节点 < 5）/ `low cost` / `normal cost` / `high cost`；**论文未给阈值，需要从数据分布推断并在报告中标注**。建议先按 `current_cost` 与“随机可行解的完成代价估计”分位数划分（例如 <Q25 low, Q25–Q75 normal, >Q75 high）。
- [ ] 写 `instruction` / `system` 模板：
  - system = `nadro.txt` / `heuristic_pool_POR.txt` 风格卡片格式说明（按实际 pool 更新 heuristic 列表）；
  - user instruction = global data feature + current state data feature + trajectory summary + “请选择 next heuristic”。
- [ ] 输出 JSON（`datasets.from_list` 可直接 load 的格式）：
  ```json
  {
    "system": "...",
    "instruction": "...",
    "reward": {
      "correct_answer": "nearest_neighbor_e8a4",
      "positive_samples": ["...", "..."],
      "negative_samples": ["..."],
      "illegal": [],
      "disabled_algorithms": [],
      "card_problem": ["tsp"],
      "card_state": ["partially visited"],
      "card_alg_type": ["exploration"],
      "card_cost": ["normal cost"]
    }
  }
  ```
- [ ] 同时生成 **vanilla GRPO 版本**（去掉 CPR/card/format 信号，只保留 outcome preference / correct answer），用于 Table 4 的 `GRPO` 消融。
- [ ] 数据质量检查：
  - 条数、字段完整率、启发式名合法率、卡片标签分布；
  - 抽 50 条人工可读打印，检查状态/标签语义；
  - 用少量样本让 Qwen 生成 10 次，统计格式符合率（不训练，纯 prompt 测试）。
- [ ] 产出 `datasets/tsp_train_s100_p2_dual.json`、`..._vanilla.json`、`dataset_stats.json`。

### 6.4 训练数据量目标
- [ ] 20 个 train case × 2 模式 × 2–3 seeds，单个 case 大约 3×N 个 round（N=4–30，很小）；预计可得到 **数千条** state-action 样本。
- [ ] 如果 < 1000 条，补充 stochastic 模式 seed 或增加 `-s` / 收集轮数；如果 > 20000 条，可下采样保持类别平衡。
- [ ] 记录样本数、正/负样本平均长度、启发式被选分布。

---

## 7. 阶段 A3：Qwen2.5-7B-Instruct-1M + GRPO + POR/CPR 训练

### 7.1 训练代码移植/修补
- [ ] 基于 recovered `src/training/`：
  - `model.py`：`model_name` 指向本地 Qwen2.5-7B-Instruct-1M；保留 LoRA target modules（q/k/v/o/gate/up/down），r=32，alpha=32，gradient checkpointing；`load_in_4bit=False`（48GB）或 True（24GB）。
  - `dataset.py`：读取我们生成的 JSON；map 成 `prompt`（system+user）+ `answer`（reward dict）；处理 train/val split。
  - `config.py`：严格用论文参数：
    - epochs=1, max_steps=-1, per_device_batch=1, grad_accum=1
    - lr=1e-6, cosine, warmup_ratio=0.1
    - optim=paged_adamw_8bit, beta1=0.9, beta2=0.99, wd=0.1, max_grad_norm=0.1
    - bf16 (或 fp16)
    - use_vllm=True, num_generations=12
    - max_prompt_length=2048, max_completion_length=768
    - save_steps 调大/只存最后；report_to 先设 `[]`，稳定后再接 wandb
  - `rewards.py`：
    - 实现/保留 `correctness_reward_func`（POR 的代码实现）、`cards_reward_func`（CPR 的代码实现）、`soft_format_reward_func`、`language_consistency_reward_func`、`algorithm_reward_func`；
    - 可选：另写 `paper_por_reward_func` 严格实现 Eq. (2)，做消融对比“代码版 POR vs 论文版 POR”；
  - `utils.py`：`ALGORITHM_NAMES` 更新为实际 P2 pool；`extract_xml_*`、卡片抽取函数保持。
- [ ] 运行目录要求：`cd src/training && python train.py` 的 import 方式需改成模块/相对路径或保持原样并用包装脚本；记录实际可跑命令。
- [ ] Dry-run：
  - 32 条样本，`max_steps=2`，`use_vllm=False`（先排除 vLLM）
  - 通过后 `use_vllm=True`，确认显存峰值和生成格式。
- [ ] 如果旧 TRL API 无法安装：移植到当前 TRL，最小改动保持 reward functions、GRPOConfig 语义不变；写 `notes/trl_port.md`。

### 7.2 训练双奖励模型（POR+CPR）
- [ ] 启动命令示例：
  ```bash
  export CUDA_VISIBLE_DEVICES=<idle_gpu_index>
  export TOKENIZERS_PARALLELISM=false
  nohup python src/training/train.py > logs/train_dual_$(date +%m%d_%H%M).log 2>&1 &
  ```
- [ ] 用 `tmux` 保持会话；日志里监控 `loss`、`reward`、`kl`、生成样例、OOM。
- [ ] 每 N 步保存 adapter（建议最后只保留 final 和少量中间点，防磁盘爆）。
- [ ] 训练中定期 `nvidia-smi`、`df -h`；若 48GB 卡 OOM：
  - 降 `max_completion_length`（但会偏离论文参数）
  - 开 gradient checkpointing
  - 降 `gpu_memory_utilization` / 调 vLLM 显存
  - 最后才考虑 QLoRA 4bit，并在报告标注偏差。
- [ ] 训练结束后保存 final LoRA adapter；可选 merge 成完整模型（`merge_and_unload`）供 vLLM serving。
- [ ] 计算训练 token 量、耗时、峰值显存、最终 loss/reward 曲线。

### 7.3 训练 vanilla GRPO（Table 4 消融）
- [ ] 同一数据/模型，只保留 outcome reward（去掉 CPR、cards、格式/语言辅助奖励中不必要的部分，保持与论文 `GRPO` 一致）；如论文 GRPO 也包含基础格式奖励，则以论文描述为准，建议做 `no_CPR` 版本并在报告说明。
- [ ] 启动独立进程/卡训练；保存 final adapter。
- [ ] 目的：复现 Table 4 的 raw 5.01 / GRPO 4.39 / POR+CPR 0.59 趋势。

### 7.4 Raw Qwen 基线
- [ ] 不训练，直接加载 base model；用同一 prompt/格式做 inference；这等价于 Table 4 的 `raw`。
- [ ] 若 raw 模型大量不按格式输出，记录 format reward / parse rate，不得人为修补输出（否则不是 zero-shot）。

### 7.5 训练验收
- [ ] 三步都完成：raw / GRPO / dual；
- [ ] 验证集上 POR+CPR 平均 gap 显著优于 GRPO 和 raw；
- [ ] 生成格式符合率（能抽出合法 heuristic name）≥ 90%（目标 100%，但需记录真实数字）；
- [ ] 语言一致性 reward 接近 1.0；
- [ ] 训练日志、adapter、merged model、配置快照归档。

---

## 8. 阶段 A4：微调选择器评测（Table 3 / Table 4 / Figure 9）

### 8.1 vLLM serving
- [ ] 启动 OpenAI-compatible server：
  ```bash
  export CUDA_VISIBLE_DEVICES=<idle_gpu_index>
  vllm serve ~/heura_repro/models/qwen25_7b_1m_dual_merged \
    --served-model-name heura-qwen-dual \
    --port 8000 --dtype bfloat16 --max-model-len 4096 \
    --gpu-memory-utilization 0.85
  ```
- [ ] 对 raw/GRPO/dual 分别起服务或按顺序评测；
- [ ] 先用一条 `curl /v1/chat/completions` 验证输出格式包含四张卡和 `selected heuristic:`。
- [ ] 若 vLLM 不兼容 Qwen2.5-1M 的 sparse attention：
  - 先试标准 Qwen2.5-7B-Instruct 的 merged adapter（如果训练时用 1M 权重则 adapter 不通用，需重训或改 base）；
  - 或尝试更新 vLLM 版本加载 1M 模型；
  - 记录 fallback 和差异。

### 8.2 评测 harness
- [ ] 实现或者复用 `find_best.py` / `GPTSelectionHyperHeuristic`：每个决策步：
  1. 模型输出卡片 + 至多 3 个候选 heuristic；
  2. 对每个候选，先执行 M=5 步；
  3. 从中间状态随机完成 T=10 条 rollout，取平均 terminal cost 作为 Q̂；
  4. 选 argmin Q̂，执行 M=5 步；
  5. 循环直到完整且无提升；单实例 2h timeout。
- [ ] `num_generations=1`（推理时不需要 GRPO 的 G 条）；温度 0.7/top-p 0.95；记录每次请求和回答。
- [ ] 并行：TTS rollout 使用 `ProcessPoolExecutor`（原代码用多进程）；同一张 GPU 可同时跑多个实例需注意显存与吞吐。
- [ ] 解析失败处理：`selected heuristic:` 缺失时回退到最近匹配名称；连续失败则记录并停止/重试；不要静默替模型决策。

### 8.3 Table 3 复现（13 instances）
- [ ] 测试实例：`kroA100, kroA150, kroB100, kroB200, kroC100, bier127, tsp225, a280, pcb442, gr666, pr152, pr1002, pr2392`。
- [ ] 方法：raw Qwen / vanilla GRPO / dual（论文 Table 3 只放 dual 与闭源 LLM 对比，Table 4 放 raw/GRPO/dual）。
- [ ] 每个实例至少 1 次，目标 3 次（论文有 ± 标准差）；结果写 `results/table3.csv`。
- [ ] 验收：dual-average ≈ 0.50%（论文），raw ≈ 5.01%，GRPO ≈ 4.39%；单实例趋势一致（尤其 kroA100/A150/B100/C100 应为 0）。
- [ ] 若部分实例达不到 0：检查 pool 是否为 P2、TTS budget 10、M=5、模型输出格式；而不是直接改论文口径。

### 8.4 Figure 9 复现（pr152）
- [ ] 对 dual model 在 `pr152` 上跑 rollout budget k = 0, 1, 2, 4, 8, 10, 20（0 表示直接用模型第一候选，不做 TTS）；
- [ ] 同样跑 raw/GRPO；
- [ ] 输出 `figures/fig9_repro.pdf`，检查 gap 随 k 下降且 dual 在所有 k 下最优。

### 8.5 评测时间与调度
- [ ] 单实例 `pr2392` 的状态数 ~2392，决策轮数 ~2*2392/5 ≈ 957；每轮 3 候选 × 10 rollouts + LLM 调用，预计单 run 分钟到数小时。
- [ ] 优先顺序：
  1. dual model 13 instances × 1 次；
  2. raw + GRPO 各 13 × 1 次；
  3. 对关键实例（tsp225, bier127, pcb442, gr666, pr152, pr1002, pr2392）补齐 3 次；
  4. Figure 9。
- [ ] 多空闲卡/多端口可以并行不同实例；每个进程用独立端口和 `CUDA_VISIBLE_DEVICES`。

---

## 9. 阶段 B1：GPT-4o 在线选择复现 Table 6 / Figure 8（需 API）

### 9.1 API 配置与决策
- [ ] 确认使用哪个模型：
  - 首选：Azure/OpenAI GPT-4o `2024-11-20`（与论文一致）；
  - 替代：用户现有 DeepSeek API（`deepseek-chat` / `deepseek-reasoner`）或本地 vLLM Qwen3-32B；
  - 记录替代模型型号、版本、调用日期。
- [ ] 确认 API key 放在服务器环境变量/配置文件，禁止写入 git。
- [ ] 先用 `chat.py` 或 `curl` 验证连通性和响应格式。
- [ ] 预算估算：
  - 每 test instance 的在线选择 API calls ≈ `ceil(N/5) + 2`（N ≈ 2×节点数）；
  - 12 个 TSP 测试 instance 合计约 5k–6k calls/run；5 个问题合计约 10k calls/run；
  - 跑 3 次 × 5 问题可能 3 万+ calls；先跑 1 次全量，再决定是否补 3 次。
- [ ] 设置 `max_attempts`、`sleep_time`、本地 cache；相同状态+候选可缓存，减少重复调用。

### 9.2 运行 pool 校准（TSP，先小后大）
- [ ] 用 P1/P2/P3 三种 pool 在 TSP 的 3–4 个代表实例上跑 `llm_hh`（GPT-4o，`-c 3 -b 10 -m 5 -n 2.0`）；
- [ ] 与论文 Table 6 的 TSP 平均值 0.50 对比，选择最接近的 pool；
- [ ] 记录 `pool_calibration.csv`；后续 5 个问题统一使用选定 pool。

### 9.3 全量运行
- [ ] 为每个 problem 建 `configs/<problem>_gpt4o.json`；
- [ ] 命令（以 core snapshot CLI 为例）：
  ```bash
  python launch_hyper_heuristic.py -p tsp -e llm_hh \
    -d output/tsp/heuristics/pool_selected \
    -l configs/tsp_gpt4o.json \
    -t kroA100.tsp,kroA150.tsp,... \
    -n 2.0 -m 5 -c 3 -b 10 -r table6_tts10
  ```
  （实际参数名以 f9ec60f CLI 为准；旧版支持 `steps_per_selection` 等命名差异需适配。）
- [ ] 每个实例可单独进程并行；统一记录 `result.txt`、LLM 调用 dump、runtime、timeout。
- [ ] 超时/失败实例标记，不当作 gap=0；可通过 `best_result` 回退，但需在报告说明。

### 9.4 汇总与验收
- [ ] 复现 Table 6 的 HeurAgenix 列（Ours），以及 Figure 8；
- [ ] 论文平均值目标：
  - TSP 0.50，CVRP 6.49，MKP 0.68，JSSP 0.25，MaxCut 0.60；
- [ ] 若偏差大：检查 pool、TTS（b=10, M=5, n=2.0）、LLM 版本、prompt、API 输出解析、timeout；
- [ ] 与论文数字写在同一张对比表里，标注“重跑值/论文值/偏差”。

### 9.5 闭源 LLM selector 对比（Table 3 的另一半）
- [ ] 用同一 harness 和同一 evolved pool 跑 GPT-4o / OpenAI o3 / DeepSeek-R1 zero-shot 选择器；如果 API 不可用则直接引用论文值并标注 †。
- [ ] 汇总到 `results/table3_llm_selectors.csv`。

---

## 10. 阶段 B2：重跑启发式演化（需 API）

> 如果用户只是想复现“方法可运行”，A 档 + released evolved heuristics 已经足够；本阶段用于“严格复现演化过程”。

### 10.1 准备
- [ ] 使用 `core_paper` 的 `evolve_heuristic.py`、`src/pipeline/heuristic_evolver.py`、`src/problems/base/prompt/*`、heuristic generator。
- [ ] 对每个 problem 的 3 个 seed 分别跑：
  - TSP：cheapest_insertion_605f / farthest_insertion_b6d3 / nearest_neighbor_f91d
  - CVRP：min_cost_insertion_048f / farthest_insertion_4e1d / nearest_neighbor_99ba
  - MKP：greedy_by_profit_8df3 / greedy_by_weight_ece2 / greedy_by_density_9e8d
  - JSSP：most_work_remaining_930e / first_come_first_served_6c4f / shortest_processing_time_first_c374
  - MaxCut：most_weight_neighbors_320c / highest_weight_edge_eb0c / balanced_cut_21d5
- [ ] 参数：train_dir=20 train cases，validation_dir=7 val cases，perturbation_ratio=0.1，perturbation_time=1000，max_refinement_round=5，filter_num=1，evolution_rounds=3。
- [ ] 实现 **API 调用计数器**：每个 seed 达到 2000 次即停止；不依赖代码内部默认轮数。
- [ ] 先做 pilot：TSP nearest_neighbor，限制 100–200 calls，检查 prompt、生成代码、smoke test、validation 是否工作；确认后并行放大。
- [ ] 每轮保存 LLM dump、生成文件、validation 结果；断点续跑（已有输出跳过）。

### 10.2 运行与验收
- [ ] 5 problems × 3 seeds，每个 seed 2000 calls；记录实际 calls、耗时、失败/回滚次数、生成文件列表；
- [ ] 对演化结果做 validation 对比 seed 的平均 gap；
- [ ] 与论文 Table 5 的“Evolved (Ours)”列对比；不要求代码逐字一致，但趋势和 gap 级别应一致；
- [ ] 若 API 预算有限，优先 TSP nearest_neighbor 演化（Table 5 有 EoH/ReEvo 对比）。
- [ ] 产出 `results/evolution_runs.csv` + `evidence/evolution_prompts/`。

### 10.3 EoH/ReEvo baseline（可选）
- [ ] clone 官方 EoH/ReEvo 仓库；
- [ ] 按论文 only TSP nearest_neighbor 接口限制，以同 GPT-4o + 2000 calls 复跑；
- [ ] 同样计 gap，与论文 17.15 / 15.94 对比。

---

## 11. 阶段 C：外部 baseline（可选，建议按需）

- [ ] **OR-Tools**：TSP/CVRP/MKP 直接写 wrapper；JSSP 用 CP-SAT；MaxCut 用 MIP/CP-SAT；2h timeout。
- [ ] **ACO**：按论文引用实现标准 ACO（TSP/CVRP/MKP/JSSP），参数与论文一致（论文未给详细参数 → 需要固定一套并做 sensitivity）。
- [ ] **GLS**：TSP GLS 实现或找开源实现，匹配 2h timeout。
- [ ] **PSO / GWO / QICSA / SS / CirCut / VNSPR**：优先找原作者代码；无法复跑的数字直接引用论文并标 †。
- [ ] 不建议默认全做 C 档；先挑 OR-Tools + ACO 做 sanity check，剩余以论文值做参考。

---

## 12. 交付物清单

- [ ] `01_文献阅读报告_HeurAgenix.md`（已生成）
- [ ] `02_复现清单_HeurAgenix.md`（本文件）
- [ ] `evidence/paper_facts.json`、`evidence/code_freeze.json`、`evidence/server_choice.json`
- [ ] `datasets/*.json` + `dataset_stats.json`
- [ ] `models/qwen25_7b_1m_{grpo,dual}/final_lora_adapters/`（或 merged）
- [ ] `results/table5_gap.csv`、`table3.csv`、`table4.csv`、`table6.csv`
- [ ] `figures/fig7_repro.pdf`、`fig8_repro.pdf`、`fig9_repro.pdf`
- [ ] `logs/train_dual.log`、`logs/train_vanilla.log`、`logs/eval_*.log`
- [ ] 一键脚本 `scripts/run_all.sh`（按阶段可断点续跑）
- [ ] `复现报告.md`：环境、命令、结果对比、偏差解释、未完成项、存储/成本
- [ ] `PROGRESS.md`：每个 checklist 项的状态（todo/doing/done/failed）

---

## 13. 资源预算

### 13.1 存储
| 项 | 估算 |
|---|---|
| 代码 + 数据 +  curated splits | < 1 GB |
| HF raw dataset | ~27 MB |
| Qwen2.5-7B-Instruct-1M bf16 | 15.24 GB |
| merged model 副本 | +15 GB（可选） |
| LoRA adapters | < 1 GB |
| 训练中间 checkpoint（受 save_steps 控制） | 2–20 GB |
| vLLM cache / compiled kernels / logs | 2–10 GB |
| 离线数据收集的 round 文件和 JSON | < 5 GB |
| 评测结果与 LLM dump | 1–10 GB |
| **建议开始前剩余** | **≥ 150 GB** |
| **训练结束保留余量** | **≥ 50 GB** |

### 13.2 GPU / CPU
- 微调：1× 48GB A6000 最合适；24GB 需 QLoRA/缩短序列（会偏离论文参数，需标注）；80GB 更稳。
- 推理：24GB 可跑 7B bf16 + vLLM（需调 gpu_memory_utilization），48GB 稳。
- 数据收集 / TTS rollout：CPU 多核 + 高内存；原代码用多进程 + `dill`，需注意 `spawn/fork`、`dill.settings['recurse']`。
- 可多卡并行：主卡训练 dual；另一张卡训练 vanilla；再一张卡做 raw/评测（不同端口或同端口不同 GPU）。

### 13.3 时间（单卡 48G，经验估计，实际以实测为准）
| 阶段 | 时间 |
|---|---|
| 环境 + 模型下载 | 1–2 天（取决于网络） |
| 数据 curation + smoke | 0.5 天 |
| Table 5 确定性复现 | 0.5 天 |
| 离线数据收集（20 cases × 2 modes × s=100） | 0.5–1 天 |
| 离线数据收集（s=1000 放大） | 2–5 天（视 CPU 核数） |
| GRPO 训练（2k–10k samples, 1 epoch） | 1–3 天 |
| raw/dual/GRPO 评测 Table 3/4/Fig9 | 2–5 天 |
| B1 LLM 选择（含 5 问题 + 3 次重复） | 3–10 天（API 限速/预算） |
| B2 演化重跑（15 seeds × 2000 calls） | 数天–数周 + API 费用 |
| C 档 baseline | 另计 |

### 13.4 API 预算
- 演化：15 个 seed × 2000 calls = 最多 3 万 calls；按 GPT-4o 价格可能几十到几百美元量级（视 token 数）；
- LLM 选择：每 run 5k–10k calls，5 问题 × 3 repeats 可到 10 万+ calls；
- 建议先 A 档零 API 打通；B1 先跑 TSP + 1 次；B2 只跑 TSP nearest_neighbor 作为样例；
- 所有 API 输出 raw dump 必须保存，避免重复调用。

---

## 14. 服务器执行策略（自动选卡 + 长任务）

- [ ] 用 2.1 脚本扫描 223–234，输出 `server_scan.txt`。
- [ ] 选卡公式：
  ```
  score = (free_mem_gb) - 2 * used_mem_gb - 0.1 * util
  ```
  在显存 ≥ 40GB 的卡里取最大；若没有，则在 24GB 卡里取最大并切 QLoRA。
- [ ] `nvidia-smi --query-compute-apps=pid,used_memory` 确认无其他用户进程；有则换卡。
- [ ] 所有长任务放 `tmux` 会话 + `nohup`，命令前 `export CUDA_VISIBLE_DEVICES=<idx>`。
- [ ] 每个任务写 `*.pid`、日志、`meta.json`；支持 `--resume`/断点跳过。
- [ ] 训练前 `df -h`；训练中每 30 分钟记录 GPU/disk；磁盘剩余 < 50GB 时自动暂停并通知。
- [ ] 不删除用户已有数据；只操作 `~/heura_repro`（或指定 `/Data/<user>/heura_repro`）。
- [ ] 结束时清理 vLLM cache/中间 checkpoint（用户确认后再删），保留结果和 adapter。

---

## 15. 需要用户确认/提供的事项

| # | 问题 | 默认建议 |
|---|---|---|
| 1 | 是否有 GPT-4o / Azure OpenAI key？用于 B1 在线选择和 B2 演化 | 若无，先做 A 档；B 档用 DeepSeek 或本地 Qwen3-32B 替代并标注 |
| 2 | 是否接受代码 freeze 为 `f9ec60f`（核心）+ `6e4fc66`（训练代码） | 建议接受；这是最接近论文的可考证版本 |
| 3 | 是否接受“训练数据自行重建”（论文未发布数据集/prompts 的精确生成脚本） | 建议接受，并保留所有推断规则文档 |
| 4 | 是否允许占用多张空闲卡并行训练/评测 | 建议允许；优先 48GB 卡 |
| 5 | 采用哪个 pool 口径：P1 / P2 / P3 | 先用 P2（Appendix E + evolved）做校准，必要时切 P3 |
| 6 | 是否需要在无法加载 Qwen2.5-7B-Instruct-1M 时回退到标准 Qwen2.5-7B | 允许，但要在报告标注 |
| 7 | 存储/目录：`~/heura_repro` 还是 `/Data/<user>/heura_repro`？ | 以服务器磁盘实际为准，优先大容量盘 |
| 8 | B2 演化 API 预算上限（例如每个 seed 2000 calls，是否全跑 15 个 seed） | 先跑 TSP nearest_neighbor 1 个 seed |
| 9 | C 档 baseline 范围 | 默认不做，或只做 OR-Tools + ACO |
| 10 | 是否允许使用 DeepSeek API（本地已有 key 可配置）作为中间替代 | 可临时替代，但论文数字对比需标注 |

---

## 16. 一页执行顺序（待用户批准后）

1. **服务器预检 + 选卡 + 检查磁盘**（2.1–2.3）。
2. **建环境 + 下载 Qwen2.5-7B-Instruct-1M**（3.3–3.5）。
3. **代码 freeze + 数据 curation + pool 构建**（0、3、4）。
4. **A1：跑 Table 5 单启发式，冻结基线数字**。
5. **A2：离线数据收集 + JSON 构建 + dry-run**。
6. **A3：dual（POR+CPR）与 vanilla GRPO 训练**。
7. **A4：raw / GRPO / dual 评测 Table 3/4 + Figure 9**。
8. **出具第一版复现报告**（A 档结果与偏差）。
9. 若用户决定继续 **B1：GPT-4o 在线选择 Table 6**。
10. 若用户决定继续 **B2：演化重跑** 和/或 **C 档 baseline**。
11. 最终交付：全部结果、模型、数据、脚本、一键重跑命令、已知不完美项。

---

**批准后我会先做 1、2 两步（预检 + 环境/模型），把选中的端口、GPU、磁盘空间、CUDA 版本和实际下载量先发给你确认，再开始 A 档训练。**
