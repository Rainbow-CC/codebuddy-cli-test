# Skill: Academic Researcher

用于指引 Agent 查询 `academic.sqlite` 数据库以回答学术研究相关的问题。

## 数据库路径
该 Skill 运行时的数据库文件位于当前 Skill 目录：
`./academic.sqlite` (相对于此 SKILL.md 的路径)

## 任务指引 (关键步骤)
为了确保查询的准确性，Agent **必须** 遵循以下流程：

1. **探索 Schema (动态发现)**: 
   在编写任何查询 SQL 之前，先使用 `sqlite3` 查询数据库的实时结构。
   - 命令示例: `sqlite3 ./academic.sqlite ".schema"` 或查询 `sqlite_master` 表。
   - **理由**: 确保字段名、外键关系和表名与实际数据库完全一致，避免幻觉。

2. **分析需求**: 根据实时 Schema 确定需要关联哪些表（如作者、论文、领域等）。

3. **编写并验证 SQL**: 根据发现的结构编写 SQL。如果遇到复杂逻辑，建议先编写简单的查询验证数据分布。

4. **整合回答**: 将查询结果转化为易于理解的自然语言。

## 核心表结构参考 (仅供参考)
*注：以下信息基于初始设计，实际请以“探索 Schema”步骤的结果为准。*
- **author (aid, name, oid)**
- **publication (pid, title, year, cid, jid, citation_num)**
- **writes (aid, pid)**: 作者与论文的撰写关系。
- **cite (citing, cited)**: 论文引用关系。
- **domain / domain_xxx**: 领域关联。

## 示例 SQL (基于参考结构)
- **查询某领域的顶尖作者**:
  ```sql
  -- 注意：执行前请确认表名和字段名是否匹配发现的 Schema
  SELECT a.name, SUM(p.citation_num) as total_citations
  FROM author a
  JOIN writes w ON a.aid = w.aid
  JOIN publication p ON w.pid = p.pid
  JOIN domain_author da ON a.aid = da.aid
  JOIN domain d ON da.did = d.did
  WHERE d.name = 'Machine Learning'
  GROUP BY a.aid
  ORDER BY total_citations DESC
  LIMIT 10;
  ```

## 注意事项
- 始终检查数据库路径是否正确。
- 对于模糊匹配，使用 `LIKE '%keyword%'`。
- 如果查询结果为空，尝试放宽搜索条件或检查拼写。
