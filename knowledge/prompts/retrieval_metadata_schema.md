# 检索元数据规范

建议每个知识块包含以下字段：

```json
{
  "document_id": "唯一文档ID",
  "title": "文档标题",
  "type": "profile | experience | project | skill | faq | policy",
  "project_slug": "agentproject | farino | myagent | mood_tracker | null",
  "visibility": "public | private",
  "confidence": "confirmed | mixed | pending",
  "importance": "primary | secondary | reference",
  "updated_at": "YYYY-MM-DD",
  "source": "MASTER_ALL | GitHub | user_confirmed"
}
```

## 过滤建议

- 公开网站仅检索 `visibility=public`。
- 求职问答优先使用 `confidence=confirmed`。
- 项目问题优先按 `project_slug` 过滤。
- `policy` 类型用于控制回答边界，不作为候选人经历内容直接输出。
