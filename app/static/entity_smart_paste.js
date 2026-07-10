(() => {
  const box = document.querySelector(".smart-paste-box");
  if (!box) return;

  const entityKey = box.dataset.entity;
  const urlInput = document.getElementById("smart-url");
  const textArea = document.getElementById("smart-paste-text");
  const fetchButton = document.getElementById("smart-fetch-button");
  const analyzeButton = document.getElementById("smart-analyze-button");
  const analyzeSelectionButton = document.getElementById("smart-analyze-selection-button");
  const clearButton = document.getElementById("smart-clear-button");
  const status = document.getElementById("smart-paste-status");
  const sourceInfo = document.getElementById("web-source-info");
  const diagnosticsBox = document.getElementById("smart-diagnostics");
  const diagnosticTitle = document.getElementById("diagnostic-title");
  const diagnosticRisk = document.getElementById("diagnostic-risk");
  const diagnosticWarnings = document.getElementById("diagnostic-warnings");
  const diagnosticAction = document.getElementById("diagnostic-action");
  const candidateSection = document.getElementById("candidate-section");
  const candidateList = document.getElementById("candidate-list");
  const clientRiskConfirmation = document.getElementById("client-risk-confirmation");
  const clientRiskConfirmCheckbox = document.getElementById("client-risk-confirm-checkbox");

  const batchToolbar = document.getElementById("people-batch-toolbar");
  const batchSelectAll = document.getElementById("batch-select-all");
  const batchSelectedCount = document.getElementById("batch-selected-count");
  const batchAnalyzeButton = document.getElementById("batch-analyze-button");
  const batchEditorSection = document.getElementById("batch-editor-section");
  const batchEditorList = document.getElementById("batch-editor-list");
  const batchDraftCount = document.getElementById("batch-draft-count");
  const batchDraftsSelectAll = document.getElementById("batch-drafts-select-all");
  const batchDraftsClearAll = document.getElementById("batch-drafts-clear-all");
  const batchSaveConfirm = document.getElementById("batch-save-confirm");
  const batchSaveButton = document.getElementById("batch-save-button");
  const batchSaveStatus = document.getElementById("batch-save-status");
  const batchSaveResults = document.getElementById("batch-save-results");
  const batchOrganizationReference = document.getElementById("batch-organization-reference");
  const batchOrganizationLookup = document.getElementById("batch-organization-lookup");
  const batchOrganizationStatus = document.getElementById("batch-organization-status");
  const batchOrganizationResults = document.getElementById("batch-organization-results");
  const batchApplyOrganization = document.getElementById("batch-apply-organization");
  const batchCreateRelations = document.getElementById("batch-create-relations");
  const batchRelationType = document.getElementById("batch-relation-type");
  const supportsPeopleBatch = entityKey === "people" && Boolean(batchToolbar);

  let fullSourceText = "";
  let currentSource = null;
  let sourceRiskHigh = false;
  let detectedCandidates = [];
  let batchDraftItems = [];
  let matchedOrganization = null;

  function setStatus(message, type = "") {
    status.textContent = message;
    status.className = type;
  }

  function setBatchStatus(message, type = "") {
    if (!batchSaveStatus) return;
    batchSaveStatus.textContent = message;
    batchSaveStatus.className = type;
  }

  function setOrganizationStatus(message, type = "") {
    if (!batchOrganizationStatus) return;
    batchOrganizationStatus.textContent = message;
    batchOrganizationStatus.className = `batch-organization-status ${type}`.trim();
  }

  function deriveOrganizationHint(title) {
    const value = (title || "").trim();
    if (!value) return "";
    const noise = ["管理团队", "核心团队", "董事会", "高管团队", "专家团队", "团队介绍", "关于我们", "领导团队"];
    const parts = value.split(/[|｜—–_-]/).map(item => item.trim()).filter(Boolean);
    const candidates = parts.filter(item => !noise.some(word => item.includes(word)) && item.length >= 2 && item.length <= 80);
    return candidates.length ? candidates[candidates.length - 1] : "";
  }

  function selectOrganization(item, applyToDrafts = false) {
    matchedOrganization = item || null;
    if (!item || !batchOrganizationReference) return;
    batchOrganizationReference.value = item.external_id || item.standard_name || "";
    setOrganizationStatus(`已匹配：${item.standard_name}（${item.external_id}）`, "success-text");
    if (batchOrganizationResults) {
      batchOrganizationResults.hidden = true;
      batchOrganizationResults.innerHTML = "";
    }
    if (applyToDrafts) applyOrganizationToDrafts();
  }

  function renderOrganizationResults(items) {
    if (!batchOrganizationResults) return;
    batchOrganizationResults.innerHTML = "";
    if (!items || !items.length) {
      batchOrganizationResults.hidden = true;
      setOrganizationStatus("未找到匹配机构。请先到“主体”模块新增机构，或关闭同步创建关系。", "error-text");
      matchedOrganization = null;
      return;
    }
    batchOrganizationResults.hidden = false;
    items.forEach(item => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "batch-org-result";
      const strong = document.createElement("strong");
      strong.textContent = item.standard_name;
      const small = document.createElement("span");
      small.textContent = `${item.external_id}${item.org_type ? " · " + item.org_type : ""}${item.region ? " · " + item.region : ""}`;
      button.append(strong, small);
      button.addEventListener("click", () => selectOrganization(item, true));
      batchOrganizationResults.appendChild(button);
    });
    setOrganizationStatus(`找到 ${items.length} 个候选，请点击正确机构。`, "loading-text");
  }

  async function lookupOrganization() {
    if (!batchOrganizationReference) return;
    const query = batchOrganizationReference.value.trim();
    if (!query) {
      setOrganizationStatus("请输入机构名称或系统编号。", "error-text");
      batchOrganizationReference.focus();
      return;
    }
    setBusy(true);
    setOrganizationStatus("正在匹配机构……", "loading-text");
    try {
      const response = await fetch(`/manage/organizations/lookup?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "机构匹配失败");
      const items = data.items || [];
      if (items.length === 1) {
        selectOrganization(items[0], false);
      } else {
        matchedOrganization = null;
        renderOrganizationResults(items);
      }
    } catch (error) {
      matchedOrganization = null;
      setOrganizationStatus(`机构匹配失败：${error.message}`, "error-text");
    } finally {
      setBusy(false);
    }
  }

  function applyOrganizationToDrafts() {
    if (!batchEditorList) return;
    const organizationName = matchedOrganization?.standard_name || batchOrganizationReference?.value.trim() || "";
    if (!organizationName) {
      setOrganizationStatus("请先匹配或输入机构。", "error-text");
      return;
    }
    let changed = 0;
    batchEditorList.querySelectorAll('[data-batch-field="organization_network"]').forEach(input => {
      if (!input.disabled) {
        input.value = organizationName;
        changed += 1;
      }
    });
    setOrganizationStatus(`已将“${organizationName}”应用到 ${changed} 条人物草稿。`, "success-text");
  }

  function setBusy(isBusy) {
    fetchButton.disabled = isBusy;
    analyzeButton.disabled = isBusy;
    analyzeSelectionButton.disabled = isBusy;
    if (batchAnalyzeButton) batchAnalyzeButton.disabled = isBusy;
    if (batchSaveButton) batchSaveButton.disabled = isBusy;
    if (batchOrganizationLookup) batchOrganizationLookup.disabled = isBusy;
    if (batchApplyOrganization) batchApplyOrganization.disabled = isBusy;
  }

  function getField(name) {
    return document.getElementById(`field-${name}`);
  }

  function fillField(name, value, {force = false} = {}) {
    if (value === null || value === undefined || value === "") return "empty";

    const field = getField(name);
    if (!field) return "missing";

    const incoming = String(value);
    const hasManualValue = field.value.trim() !== "" && field.dataset.smartFilled !== "true";
    if (hasManualValue && !force && field.tagName !== "SELECT") {
      return "skipped";
    }

    if (field.tagName === "SELECT") {
      const exists = Array.from(field.options).some(option => option.value === incoming);
      if (!exists) return "skipped";
      field.value = incoming;
    } else {
      field.value = incoming;
    }

    field.dataset.smartFilled = "true";
    field.classList.add("smart-filled");
    setTimeout(() => field.classList.remove("smart-filled"), 1600);
    return "filled";
  }

  function preserveSource(result) {
    fullSourceText = result.text || "";
    currentSource = result;
    fillField("source_url", result.url || urlInput.value.trim(), {force: true});
    fillField("source_type", "公开网页", {force: true});
    fillField("source_title", result.title || "", {force: true});
    fillField("source_text", fullSourceText, {force: true});
  }

  function riskLabel(level) {
    if (level === "high") return "高风险：疑似多主体";
    if (level === "medium") return "需重点核对";
    return "可继续人工核对";
  }

  function renderDiagnostics(diagnostics) {
    if (!diagnostics) {
      diagnosticsBox.hidden = true;
      candidateSection.hidden = true;
      resetBatchCandidateControls();
      return;
    }

    diagnosticsBox.hidden = false;
    diagnosticTitle.textContent = diagnostics.page_mode === "multiple_subjects"
      ? "检测到多主体页面"
      : diagnostics.page_mode === "single_subject"
        ? "检测到单主体内容"
        : "主体数量无法稳定判断";
    diagnosticRisk.textContent = riskLabel(diagnostics.risk_level);
    diagnosticRisk.className = `risk-badge risk-${diagnostics.risk_level}`;

    diagnosticWarnings.innerHTML = "";
    (diagnostics.warnings || []).forEach(message => {
      const item = document.createElement("li");
      item.textContent = message;
      diagnosticWarnings.appendChild(item);
    });
    if (!(diagnostics.warnings || []).length) {
      const item = document.createElement("li");
      item.textContent = "未发现明显多主体特征，但字段仍需人工核对。";
      diagnosticWarnings.appendChild(item);
    }
    diagnosticAction.textContent = diagnostics.recommended_action || "";

    renderCandidates(diagnostics.candidates || []);
    if (diagnostics.risk_level === "high") {
      sourceRiskHigh = true;
    }
    if (clientRiskConfirmation) {
      clientRiskConfirmation.hidden = !sourceRiskHigh;
      if (clientRiskConfirmCheckbox) clientRiskConfirmCheckbox.required = sourceRiskHigh;
    }
  }

  function resetBatchCandidateControls() {
    detectedCandidates = [];
    if (batchToolbar) batchToolbar.hidden = true;
    if (batchSelectedCount) batchSelectedCount.textContent = "已选择 0 条";
  }

  function updateCandidateSelectionCount() {
    if (!supportsPeopleBatch) return;
    const checkboxes = Array.from(candidateList.querySelectorAll(".candidate-select"));
    const selected = checkboxes.filter(item => item.checked).length;
    batchSelectedCount.textContent = `已选择 ${selected} 条 / 共 ${checkboxes.length} 条`;
    batchSelectAll.checked = Boolean(checkboxes.length) && selected === checkboxes.length;
    batchSelectAll.indeterminate = selected > 0 && selected < checkboxes.length;
    batchAnalyzeButton.disabled = selected === 0;
  }

  function renderCandidates(candidates) {
    candidateList.innerHTML = "";
    detectedCandidates = candidates.slice(0, 30);
    if (!detectedCandidates.length) {
      candidateSection.hidden = true;
      resetBatchCandidateControls();
      return;
    }

    candidateSection.hidden = false;
    if (supportsPeopleBatch) batchToolbar.hidden = false;

    detectedCandidates.forEach((candidate, index) => {
      const card = document.createElement("article");
      card.className = supportsPeopleBatch ? "candidate-card batch-candidate-card" : "candidate-card";

      if (supportsPeopleBatch) {
        const selectWrap = document.createElement("label");
        selectWrap.className = "candidate-check";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "candidate-select";
        checkbox.dataset.candidateIndex = String(index);
        checkbox.checked = true;
        checkbox.addEventListener("change", updateCandidateSelectionCount);
        const selectText = document.createElement("span");
        selectText.textContent = "选入批量处理";
        selectWrap.append(checkbox, selectText);
        card.appendChild(selectWrap);
      }

      const body = document.createElement("div");
      body.className = "candidate-body";
      const title = document.createElement("strong");
      title.textContent = `${index + 1}. ${candidate.label || "未命名候选"}`;
      const subtitle = document.createElement("p");
      subtitle.textContent = candidate.subtitle || "";
      const preview = document.createElement("small");
      preview.textContent = (candidate.text || "").replace(/\n/g, " ").slice(0, 180);
      body.append(title, subtitle, preview);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary candidate-use-button";
      button.textContent = "单条使用并分析";
      button.addEventListener("click", async () => {
        textArea.value = candidate.text || "";
        textArea.focus();
        await analyzeText(candidate.text || "", true);
      });

      card.append(body, button);
      candidateList.appendChild(card);
    });

    updateCandidateSelectionCount();
  }

  async function analyzeText(text, fromCandidate = false) {
    const value = (text || "").trim();
    if (value.length < 10) {
      setStatus("请先读取网页、粘贴文字，或至少选中10个字符。", "error-text");
      return;
    }

    setBusy(true);
    setStatus("正在判断主体数量并生成候选字段……", "loading-text");

    try {
      const response = await fetch(`/manage/${entityKey}/analyze`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: value}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "分析失败");

      renderDiagnostics(data.diagnostics);
      if (data.diagnostics && !data.diagnostics.fill_allowed) {
        setStatus("检测到多主体：已停止自动填表，请先选择单条候选或选中文字。", "error-text");
        return;
      }

      let filled = 0;
      let skipped = 0;
      Object.entries(data.fields || {}).forEach(([name, fieldValue]) => {
        const result = fillField(name, fieldValue);
        if (result === "filled") filled += 1;
        if (result === "skipped") skipped += 1;
      });

      if (fromCandidate) {
        setStatus(`已按单条候选填入 ${filled} 个字段，请逐项核对后保存。`, "success-text");
      } else if (skipped) {
        setStatus(`已填入 ${filled} 个字段；${skipped} 个已有内容的字段未覆盖。`, "success-text");
      } else {
        setStatus(`已填入 ${filled} 个字段，请逐项核对后保存。`, "success-text");
      }
    } catch (error) {
      setStatus(`分析失败：${error.message}`, "error-text");
    } finally {
      setBusy(false);
    }
  }

  function createTextField(labelText, fieldName, value, rows = 0) {
    const label = document.createElement("label");
    label.className = "batch-field";
    const caption = document.createElement("span");
    caption.textContent = labelText;
    let input;
    if (rows > 0) {
      input = document.createElement("textarea");
      input.rows = rows;
    } else {
      input = document.createElement("input");
      input.type = "text";
    }
    input.dataset.batchField = fieldName;
    input.value = value || "";
    label.append(caption, input);
    return label;
  }

  function renderMessageList(messages, className) {
    if (!messages || !messages.length) return null;
    const list = document.createElement("ul");
    list.className = className;
    messages.forEach(message => {
      const item = document.createElement("li");
      item.textContent = message;
      list.appendChild(item);
    });
    return list;
  }

  function updateBatchDraftCount() {
    if (!batchEditorList || !batchDraftCount) return;
    const all = Array.from(batchEditorList.querySelectorAll(".batch-save-select:not(:disabled)"));
    const selected = all.filter(item => item.checked).length;
    batchDraftCount.textContent = `已勾选 ${selected} 条 / 共 ${batchDraftItems.length} 条草稿`;
  }

  function renderBatchEditors(items) {
    batchDraftItems = items || [];
    batchEditorList.innerHTML = "";
    batchSaveResults.hidden = true;
    batchSaveResults.innerHTML = "";
    batchSaveConfirm.checked = false;
    setBatchStatus("");

    if (!batchDraftItems.length) {
      batchEditorSection.hidden = true;
      return;
    }

    batchEditorSection.hidden = false;
    batchDraftItems.forEach((item, index) => {
      const fields = item.fields || {};
      const duplicateMatches = item.duplicate_matches || [];
      const article = document.createElement("article");
      article.className = "batch-person-card";
      article.dataset.draftIndex = String(index);

      const top = document.createElement("div");
      top.className = "batch-person-top";

      const selectLabel = document.createElement("label");
      selectLabel.className = "batch-person-select";
      const selector = document.createElement("input");
      selector.type = "checkbox";
      selector.className = "batch-save-select";
      selector.checked = Boolean(item.can_save && !duplicateMatches.length);
      selector.disabled = Boolean(item.batch_duplicate || (item.errors || []).length);
      selector.addEventListener("change", updateBatchDraftCount);
      const heading = document.createElement("strong");
      heading.textContent = `${index + 1}. ${fields.name || "未识别姓名"}`;
      selectLabel.append(selector, heading);

      const state = document.createElement("span");
      state.className = "batch-state-badge";
      if ((item.errors || []).length) {
        state.classList.add("batch-state-error");
        state.textContent = "需修正";
      } else if (item.batch_duplicate) {
        state.classList.add("batch-state-error");
        state.textContent = "批次重复";
      } else if (duplicateMatches.length) {
        state.classList.add("batch-state-warning");
        state.textContent = "已有同名";
      } else {
        state.classList.add("batch-state-ready");
        state.textContent = "可保存";
      }
      top.append(selectLabel, state);
      article.appendChild(top);

      const errors = renderMessageList(item.errors || [], "batch-message-list batch-errors");
      if (errors) article.appendChild(errors);
      const warnings = renderMessageList(item.warnings || [], "batch-message-list batch-warnings");
      if (warnings) article.appendChild(warnings);

      if (duplicateMatches.length) {
        const duplicateBox = document.createElement("div");
        duplicateBox.className = "batch-duplicate-box";
        const text = document.createElement("span");
        text.textContent = "同名记录：";
        duplicateBox.appendChild(text);
        duplicateMatches.forEach((match, matchIndex) => {
          const link = document.createElement("a");
          link.href = match.url;
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = `${match.external_id || "#" + match.id} ${match.name}${match.same_organization ? "（同一机构）" : ""}`;
          duplicateBox.appendChild(link);
          if (matchIndex < duplicateMatches.length - 1) duplicateBox.append("、");
        });

        const allowLabel = document.createElement("label");
        allowLabel.className = "batch-allow-duplicate";
        const allowInput = document.createElement("input");
        allowInput.type = "checkbox";
        allowInput.className = "batch-allow-duplicate-input";
        const allowText = document.createElement("span");
        allowText.textContent = "确认是不同人物，同名仍保存";
        allowLabel.append(allowInput, allowText);
        duplicateBox.appendChild(allowLabel);
        article.appendChild(duplicateBox);
      }

      const fieldGrid = document.createElement("div");
      fieldGrid.className = "batch-field-grid";
      fieldGrid.append(
        createTextField("姓名 *", "name", fields.name || ""),
        createTextField("公开职位", "public_role", fields.public_role || "", 2),
        createTextField("当前机构/网络", "organization_network", fields.organization_network || "", 2),
        createTextField("能力标签", "ability_tags", fields.ability_tags || "", 2),
        createTextField("价值与经验摘要", "value_provided", fields.value_provided || "", 5),
      );
      article.appendChild(fieldGrid);

      const sourceDetails = document.createElement("details");
      sourceDetails.className = "batch-source-details";
      const summary = document.createElement("summary");
      summary.textContent = "查看该人物来源片段";
      const pre = document.createElement("pre");
      pre.textContent = item.source_text || fields.source_text || "";
      sourceDetails.append(summary, pre);
      article.appendChild(sourceDetails);

      batchEditorList.appendChild(article);
    });

    updateBatchDraftCount();
    batchEditorSection.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function selectedCandidatePayload() {
    return Array.from(candidateList.querySelectorAll(".candidate-select:checked"))
      .map(checkbox => detectedCandidates[Number(checkbox.dataset.candidateIndex)])
      .filter(Boolean)
      .slice(0, 30);
  }

  async function analyzeSelectedCandidates() {
    const selected = selectedCandidatePayload();
    if (!selected.length) {
      setStatus("请至少勾选一个人物候选。", "error-text");
      return;
    }

    setBusy(true);
    setStatus(`正在批量解析 ${selected.length} 个人物候选……`, "loading-text");
    try {
      const response = await fetch("/manage/people/batch-analyze", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          candidates: selected,
          source_url: currentSource?.url || urlInput.value.trim() || getField("source_url")?.value || "",
          source_title: currentSource?.title || getField("source_title")?.value || "",
          organization_hint: batchOrganizationReference?.value.trim() || deriveOrganizationHint(currentSource?.title || getField("source_title")?.value || ""),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "批量解析失败");
      if (data.organization_match) {
        selectOrganization(data.organization_match, false);
      } else if ((data.organization_candidates || []).length > 1) {
        renderOrganizationResults(data.organization_candidates);
      }
      renderBatchEditors(data.items || []);
      if (matchedOrganization) applyOrganizationToDrafts();
      setStatus(`已生成 ${data.count || 0} 条人物草稿。请在下方逐条核对后批量保存。`, "success-text");
    } catch (error) {
      setStatus(`批量解析失败：${error.message}`, "error-text");
    } finally {
      setBusy(false);
    }
  }

  function collectSelectedBatchItems() {
    const cards = Array.from(batchEditorList.querySelectorAll(".batch-person-card"));
    const payloadItems = [];
    const submittedCards = [];
    cards.forEach(card => {
      const selector = card.querySelector(".batch-save-select");
      if (!selector || !selector.checked || selector.disabled) return;
      const draftIndex = Number(card.dataset.draftIndex);
      const draft = batchDraftItems[draftIndex] || {};
      const fieldValue = name => card.querySelector(`[data-batch-field="${name}"]`)?.value.trim() || "";
      payloadItems.push({
        name: fieldValue("name"),
        public_role: fieldValue("public_role"),
        organization_network: fieldValue("organization_network"),
        ability_tags: fieldValue("ability_tags"),
        value_provided: fieldValue("value_provided"),
        source_url: draft.fields?.source_url || currentSource?.url || urlInput.value.trim() || "",
        source_title: draft.fields?.source_title || currentSource?.title || "",
        source_text: draft.source_text || draft.fields?.source_text || "",
        allow_duplicate: Boolean(card.querySelector(".batch-allow-duplicate-input")?.checked),
      });
      submittedCards.push(card);
    });
    return {payloadItems, submittedCards};
  }

  function renderBatchSaveResults(data, submittedCards) {
    batchSaveResults.innerHTML = "";
    batchSaveResults.hidden = false;

    if ((data.created || []).length) {
      const section = document.createElement("div");
      section.className = "batch-result-success";
      const title = document.createElement("strong");
      title.textContent = `成功保存 ${data.created_count} 人：`;
      section.appendChild(title);
      const list = document.createElement("ul");
      data.created.forEach(item => {
        const row = document.createElement("li");
        const link = document.createElement("a");
        link.href = item.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = `${item.external_id} ${item.name}`;
        row.appendChild(link);
        if (item.relation) {
          row.append(` · 已${item.relation.created ? "创建" : "保留"}${item.relation.relation_type}关系 → ${item.relation.organization_name}`);
        }
        if (item.warning) {
          const warning = document.createElement("span");
          warning.className = "batch-result-warning";
          warning.textContent = ` · ${item.warning}`;
          row.appendChild(warning);
        }
        list.appendChild(row);
        const card = submittedCards[item.index];
        if (card) {
          card.classList.add("batch-saved");
          const selector = card.querySelector(".batch-save-select");
          if (selector) {
            selector.checked = false;
            selector.disabled = true;
          }
          card.querySelectorAll("input, textarea").forEach(input => { input.disabled = true; });
          const badge = card.querySelector(".batch-state-badge");
          if (badge) {
            badge.className = "batch-state-badge batch-state-saved";
            badge.textContent = "已保存";
          }
        }
      });
      section.appendChild(list);
      batchSaveResults.appendChild(section);
    }

    if ((data.skipped || []).length) {
      const section = document.createElement("div");
      section.className = "batch-result-skipped";
      const title = document.createElement("strong");
      title.textContent = `跳过 ${data.skipped_count} 人：`;
      section.appendChild(title);
      const list = document.createElement("ul");
      data.skipped.forEach(item => {
        const row = document.createElement("li");
        row.textContent = `${item.name || "未命名"}：${item.reason}`;
        list.appendChild(row);
      });
      section.appendChild(list);
      batchSaveResults.appendChild(section);
    }

    updateBatchDraftCount();
  }

  async function saveSelectedBatchPeople() {
    if (!batchSaveConfirm.checked) {
      setBatchStatus("请先勾选“我已逐条核对”。", "error-text");
      batchSaveConfirm.focus();
      return;
    }

    const {payloadItems, submittedCards} = collectSelectedBatchItems();
    if (!payloadItems.length) {
      setBatchStatus("没有勾选可保存的人物。", "error-text");
      return;
    }
    const missingName = payloadItems.find(item => !item.name);
    if (missingName) {
      setBatchStatus("存在空姓名，请补充后再保存。", "error-text");
      return;
    }
    if (batchCreateRelations?.checked && !batchOrganizationReference?.value.trim()) {
      setBatchStatus("已启用同步创建关系，请先匹配关联机构；也可以取消该选项后仅保存人物。", "error-text");
      batchOrganizationReference?.focus();
      return;
    }

    setBusy(true);
    setBatchStatus(`正在保存 ${payloadItems.length} 人……`, "loading-text");
    try {
      const response = await fetch("/manage/people/batch-save", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          confirmed: true,
          items: payloadItems,
          organization_reference: batchOrganizationReference?.value.trim() || "",
          relation_type: batchRelationType?.value || "任职",
          create_relations: Boolean(batchCreateRelations?.checked),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "批量保存失败");
      renderBatchSaveResults(data, submittedCards);
      const relationNote = data.organization
        ? `，并创建/保留 ${data.relations_created || 0} 条人物-机构关系`
        : "";
      if (data.skipped_count) {
        setBatchStatus(`已保存 ${data.created_count} 人${relationNote}，跳过 ${data.skipped_count} 人。请查看下方结果。`, "error-text");
      } else {
        setBatchStatus(`已成功保存 ${data.created_count} 人${relationNote}。`, "success-text");
      }
    } catch (error) {
      setBatchStatus(`批量保存失败：${error.message}`, "error-text");
    } finally {
      setBusy(false);
    }
  }

  fetchButton.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      setStatus("请先粘贴网页链接。", "error-text");
      return;
    }

    setBusy(true);
    setStatus("正在读取网页正文……", "loading-text");
    sourceInfo.hidden = true;

    try {
      const response = await fetch("/manage/fetch-webpage", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url, entity_key: entityKey}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "网页读取失败");

      const result = data.result;
      const combined = [
        result.title ? `标题：${result.title}` : "",
        result.published_at ? `发布日期：${result.published_at}` : "",
        result.text || "",
      ].filter(Boolean).join("\n");

      textArea.value = combined;
      preserveSource(result);
      if (supportsPeopleBatch && batchOrganizationReference && !batchOrganizationReference.value.trim()) {
        const hint = deriveOrganizationHint(result.title || "");
        if (hint) {
          batchOrganizationReference.value = hint;
          setOrganizationStatus(`已从网页标题推测机构“${hint}”，批量保存前请点击“检查机构”。`, "loading-text");
        }
      }
      sourceInfo.textContent = `已保留来源：${result.title || result.url}｜正文 ${result.content_length} 字`;
      sourceInfo.hidden = false;
      renderDiagnostics(data.diagnostics);

      if (data.diagnostics && data.diagnostics.risk_level === "high") {
        if (supportsPeopleBatch && (data.diagnostics.candidates || []).length > 1) {
          setStatus(`网页读取成功，检测到 ${data.diagnostics.candidates.length} 个人物候选。可全选后批量解析。`, "success-text");
        } else {
          setStatus("网页读取成功，但检测到多主体。请选择下方单条候选，不会自动填表。", "error-text");
        }
      } else {
        setStatus("网页读取成功。请确认内容后点击“分析当前内容”。", "success-text");
      }
    } catch (error) {
      setStatus(`读取失败：${error.message} 可直接复制网页正文。`, "error-text");
    } finally {
      setBusy(false);
    }
  });

  analyzeButton.addEventListener("click", () => analyzeText(textArea.value));

  analyzeSelectionButton.addEventListener("click", () => {
    const start = textArea.selectionStart;
    const end = textArea.selectionEnd;
    const selected = textArea.value.slice(start, end).trim();
    if (!selected) {
      setStatus("请先在“待分析文字”中拖动选中一段单主体内容。", "error-text");
      textArea.focus();
      return;
    }
    analyzeText(selected, true);
  });

  if (supportsPeopleBatch) {
    batchSelectAll.addEventListener("change", () => {
      candidateList.querySelectorAll(".candidate-select").forEach(checkbox => {
        checkbox.checked = batchSelectAll.checked;
      });
      updateCandidateSelectionCount();
    });
    batchAnalyzeButton.addEventListener("click", analyzeSelectedCandidates);
    batchOrganizationLookup?.addEventListener("click", lookupOrganization);
    batchOrganizationReference?.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        lookupOrganization();
      }
    });
    batchOrganizationReference?.addEventListener("input", () => {
      matchedOrganization = null;
      if (batchOrganizationResults) batchOrganizationResults.hidden = true;
    });
    batchApplyOrganization?.addEventListener("click", applyOrganizationToDrafts);
    batchDraftsSelectAll.addEventListener("click", () => {
      batchEditorList.querySelectorAll(".batch-save-select:not(:disabled)").forEach(checkbox => {
        checkbox.checked = true;
      });
      updateBatchDraftCount();
    });
    batchDraftsClearAll.addEventListener("click", () => {
      batchEditorList.querySelectorAll(".batch-save-select:not(:disabled)").forEach(checkbox => {
        checkbox.checked = false;
      });
      updateBatchDraftCount();
    });
    batchSaveButton.addEventListener("click", saveSelectedBatchPeople);
  }

  clearButton.addEventListener("click", () => {
    urlInput.value = "";
    textArea.value = "";
    fullSourceText = "";
    currentSource = null;
    sourceRiskHigh = false;
    sourceInfo.hidden = true;
    sourceInfo.textContent = "";
    diagnosticsBox.hidden = true;
    candidateSection.hidden = true;
    candidateList.innerHTML = "";
    resetBatchCandidateControls();
    batchDraftItems = [];
    if (batchEditorSection) batchEditorSection.hidden = true;
    if (batchEditorList) batchEditorList.innerHTML = "";
    if (batchSaveResults) {
      batchSaveResults.hidden = true;
      batchSaveResults.innerHTML = "";
    }
    if (batchSaveConfirm) batchSaveConfirm.checked = false;
    if (batchOrganizationReference) batchOrganizationReference.value = "";
    if (batchCreateRelations) batchCreateRelations.checked = true;
    if (batchRelationType) batchRelationType.value = "任职";
    matchedOrganization = null;
    if (batchOrganizationResults) {
      batchOrganizationResults.hidden = true;
      batchOrganizationResults.innerHTML = "";
    }
    setOrganizationStatus("");
    setBatchStatus("");
    if (clientRiskConfirmation) clientRiskConfirmation.hidden = true;
    if (clientRiskConfirmCheckbox) {
      clientRiskConfirmCheckbox.checked = false;
      clientRiskConfirmCheckbox.required = false;
    }
    setStatus("");
  });
})();
