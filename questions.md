测试题一：跨实体的领域查询与聚合
问题：
> “请帮我统计一下，在 'Machine Learning'
> 这个领域（domain）中，哪些机构（organization）发表的论文总引用数（citation_num）排名前
> 5？请列出机构名称和对应的总引用数。”

Skill 测试点：

* Agent 必须发现论文和领域是通过 domain_publication 表进行多对多关联的，而不是在论文表里找领域。
* 必须理清关联链条：organization -> author -> writes -> publication -> domain_publication ->
  domain。

标准答案 (预期的 SQL)：

```sql
SELECT o.name, SUM(p.citation_num) AS total_citations
FROM organization o
         JOIN author a ON o.oid = a.oid
         JOIN writes w ON a.aid = w.aid
         JOIN publication p ON w.pid = p.pid
         JOIN domain_publication dp ON p.pid = dp.pid
         JOIN domain d ON dp.did = d.did
WHERE d.name = 'Machine Learning'
GROUP BY o.oid
ORDER BY total_citations DESC LIMIT 5;
```

---

测试题二：自连接与引用关系分析
问题：
> “我想知道论文《Attention Is All You
> Need》引用了哪些其他论文，并且我想知道那些被引用的论文中有多少篇是发表在期刊（journal）上的而不是
> 会议上的。请返回这些被引用且发在期刊上的论文标题。”

Skill 测试点：

* Agent 必须仔细查看 cite 表的 Schema（citing 引用了 cited），弄清引用方向。
* 必须理解如何区分期刊论文和会议论文：在 publication 表中，如果关联了期刊，其 jid 不为空（或 cid
  为空）。

标准答案 (预期的 SQL)：

````sql
SELECT p_cited.title
FROM publication p_citing
         JOIN cite c ON p_citing.pid = c.citing
         JOIN publication p_cited ON c.cited = p_cited.pid
WHERE p_citing.title = 'Attention Is All You Need'
  AND p_cited.jid IS NOT NULL;
````

---

测试题三：多重约束条件下的交叉过滤
问题：
> “请找出那些同时在 'Computer Vision' 领域和 'Natural Language Processing'
> 领域都作为关键词（keyword）出现过的词汇。请列出这些关键词的文本。”

Skill 测试点：

* Agent 不能凭直觉使用 keyword.domain = ...。
* 必须遵循指引探索出 domain_keyword 这个特定的中间映射表。
* 必须懂得使用集合交集（INTERSECT）或子查询来寻找同时满足两个多对多关联条件的实体。

标准答案 (预期的 SQL)：

````sql
SELECT k.keyword
FROM keyword k
         JOIN domain_keyword dk1 ON k.kid = dk1.kid
         JOIN domain d1 ON dk1.did = d1.did
WHERE d1.name = 'Computer Vision'
INTERSECT
SELECT k.keyword
FROM keyword k
         JOIN domain_keyword dk2 ON k.kid = dk2.kid
         JOIN domain d2 ON dk2.did = d2.did
WHERE d2.name = 'Natural Language Processing';

````

为什么这些问题能验证 Skill？
如果你用一个没有挂载此 Skill 的 Agent 去回答，它大概率会写出 SELECT * FROM keywords WHERE domain
IN (...) 这样凭空捏造字段的错误 SQL。而挂载了此 Skill 的 Agent，会因为第一条指令“探索 Schema
(动态发现)”的强制约束，先执行 .schema 去看清真实的表关联，从而输出上述完全正确的标准答案。