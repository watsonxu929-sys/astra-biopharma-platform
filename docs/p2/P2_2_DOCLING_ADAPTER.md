# P2.2 Docling 适配器

依赖独立维护在 `requirements-docling.txt`，延迟导入。未安装、附件缺失和超大文件分别返回明确状态，不影响主应用。默认文件上限20MB。

适配器保留文件名、MIME、原始URL、SHA256、文件大小、页数、章节、表格行列和页码定位；表格以结构化JSON保存，不拼接成不可读长文本。空正文返回 `ocr_required`，不生成虚假正文。

真实结果：FDA PDF 36页，解析成功；FDA XLSX 解析成功并保留结构化表格。PDF预处理曾出现部分页面 `std::bad_alloc` 和 RapidOCR空结果告警，但整体解析成功，列入人工复核风险。本轮未把OCR设为强制业务能力。
