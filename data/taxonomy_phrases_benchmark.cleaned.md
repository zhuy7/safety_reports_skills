# taxonomy_phrases_benchmark 清洗说明

## 产物

- 原始数据：`taxonomy_phrases_benchmark评测.jsonl`
- 清洗后数据：`taxonomy_phrases_benchmark.cleaned.jsonl`
- 问题报告：`taxonomy_phrases_benchmark.issues.json`
- 清洗脚本：`../scripts/clean_taxonomy_benchmark.py`

## 本次清洗做了什么

本次清洗的目标是生成“可直接用于训练”的版本，但不擅自修改人工标注的语义判断。

已执行的清洗规则：

1. 修复结构错误的 JSONL 行。
2. 对 `in_taxonomy = false` 的样本，统一规范为：
   - `layer = null`
   - `score = null`
3. 对完全重复且标签一致的短语去重，只保留第一条。
4. 保留所有正样本的原始 `layer` 和 `score` 标注，不做语义重标。

## 本次清洗没有做什么

以下问题已经在问题报告中标明，但这次没有直接改写人工标签：

1. `score` 的语义方向存在歧义。
   - prompt 文案写的是“分值越高越抽象”
   - 但样本例子和大量实际标注更接近“分值越高越具体”
2. `in_taxonomy` 的判定边界仍然带有一定任务定义色彩。
   - 一些“措施类”“建议类”“治理动作类”短语被判为负样本
   - 但少量管理类概括短语又被判为正样本
3. 数据分布不均衡。
   - 负样本偏多
   - 正样本中 `管` 层面占比明显更高
   - `score=1` 当前缺失

## 推荐解释方式

如果你现在要直接拿这份清洗版做训练，建议在训练说明里明确写成：

- `in_taxonomy`：短语是否可作为 taxonomy 元素
- `layer`：短语所属层面，取值为 `人/物/环/管`
- `score`：沿用当前人工标注分值，但其实际语义更接近“粒度/具体程度等级”，而不是严格意义上的“抽象程度”

更稳妥的字段命名建议：

- 将训练内部使用的 `score` 重命名为 `granularity_level`
- 或命名为 `specificity_level`

这样可以避免后续模型把“高分 = 更抽象”学反。

## 清洗后数据概况

以 `taxonomy_phrases_benchmark.cleaned.jsonl` 为准：

- 总条数：255
- `in_taxonomy = true`：109
- `in_taxonomy = false`：146

正样本层面分布：

- `人`：25
- `物`：16
- `环`：8
- `管`：60

正样本分值分布：

- `2`：5
- `3`：12
- `4`：30
- `5`：62

## 使用建议

这份清洗版适合先做三类监督任务：

1. `in_taxonomy` 二分类
2. `layer` 四分类
3. `score/granularity` 等级预测

但不建议直接把 `score` 当作层次树结构本身。更推荐的做法是：

1. 先预测短语是否属于 taxonomy
2. 再预测所属层面
3. 再预测语义粒度等级
4. 最后单独做父子关系判断或候选父节点排序

## 后续建议

如果你要把这份数据继续升级为“建树训练集”，下一步最值得补的是两类标注：

1. 增补 `score=1` 的典型样本
2. 新增“父短语 / 子短语 / 是否成立”的关系型样本

后者会比继续堆单点打分样本更直接提升层次建立质量。
