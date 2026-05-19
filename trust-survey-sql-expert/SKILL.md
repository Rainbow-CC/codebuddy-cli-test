# Trust Survey SQL Expert

本 Skill 旨在指导 Agent 通过 SQLite 数据库 `trust_survey.db` 获取中国信托业（65家公司）的科技建设统计数据。

## 核心资源

- **数据库文件**: `trust_survey.db` （在当前skill根目录下）
- **主数据表**: `survey_data` (包含所有调研详情)
- **元数据表**: `metadata` (字段名与原始问题的映射关系)

## 辅助参考资源的使用

除了直接查询 `metadata` 表，Agent 还可以利用 `references/column_mapping.csv`：

1. **快速预览**: 在执行 SQL 前，可以读取此 CSV 文件来理解整个问卷的结构和字段分布。
2. **上下文检索**: 对于无法直接操作 SQL 的 Agent，此文件可作为 Prompt 的一部分，帮助其识别正确的字段 ID。
3. **备用方案**: 当数据库表结构受损或无法访问时，此文件是字段映射的唯一权威来源。

## 数据查询策略 (两步走)

为了确保查询准确，Agent 必须遵循以下流程：

### 1. 查找目标字段 (Keyword Search)

由于字段名（如 `c36_...`）是生成的，Agent 必须先在 `metadata` 表中查找关键词以获取正确的 `column_id`。由于数据量不大，可以查询全量数据。

**SQL 示例:**

```sql
SELECT column_id, original_question 
FROM metadata 
WHERE original_question LIKE '%外包%' OR original_question LIKE '%投入%';
```

### 2. 执行数据统计

获取 `column_id` 后，直接对 `survey_data` 表执行 SQL 聚合或筛选。

**常见场景 SQL 模板:**

- **Top N 排名:**
  
  ```sql
  SELECT c1_公司简称, [COLUMN_ID] 
  FROM survey_data 
  ORDER BY [COLUMN_ID] DESC 
  LIMIT 10;
  ```

- **行业平均水平:**
  
  ```sql
  SELECT AVG([COLUMN_ID]) as 行业平均值 
  FROM survey_data;
  ```

- **占比统计 (如信创进度):**
  
  ```sql
  SELECT c1_公司简称, [COLUMN_ID] 
  FROM survey_data 
  WHERE [COLUMN_ID] > 50;
  ```

- **多维度筛选:**
  
  ```sql
  -- 查找在北京且外包人数大于 50 的公司
  SELECT c1_公司简称 
  FROM survey_data 
  WHERE c1_公司简称 IN (SELECT c1_公司简称 FROM survey_data WHERE [REGION_COL] = '北京')
    AND [OUTSOURCING_COL] > 50;
  ```

## 字段命名规范提示

- `c0_拼音序`
- `c1_公司简称`
- `c13`, `c14`, `c15`: 2023-2025 科技投入 (万元)
- `c36`: 科技外包团队总人数
- `c21`: 自有科技团队总人数
- `c87`: ISO 27001 认证情况 (1 表示已获得)

## 注意事项

1. **空值处理**: 部分公司未填写某些项，SQL 查询时注意使用 `WHERE [COLUMN_ID] IS NOT NULL`。
2. **模糊匹配**: 公司简称搜索时建议使用 `LIKE '%公司名%'`。
3. **元数据依赖**: 永远先查 `metadata`，不要假设字段 ID 永远不变。
4. **专注于用户的问题**: 仅回答用户问题，不回答数据库搜索细节。
