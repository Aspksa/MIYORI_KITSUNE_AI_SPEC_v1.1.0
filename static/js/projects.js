async function renderEmployeesModule(project, module) {
  showWorkspaceShell("work", 'АО "Примавтодор"', "Сотрудники", "Кадровые сведения сотрудников проекта.");
  workspaceBody.innerHTML =
    '<section class="workspace-card workspace-card-wide employee-module">' +
      '<div class="workspace-card-head"><div><strong>Сотрудники</strong><small>ФИО, отдел, должность и номер топливной карты</small></div>' +
      '<span id="employeeCount" class="soft-status neutral">0 сотрудников</span></div>' +
      '<form id="employeeForm" class="employee-form">' +
        '<input id="employeeId" type="hidden">' +
        '<label><span>ФИО</span><input id="employeeFullName" type="text" required placeholder="Иванов Иван Иванович"></label>' +
        '<label><span>Отдел</span><input id="employeeDepartment" type="text" placeholder="Отдел"></label>' +
        '<label><span>Должность</span><input id="employeePosition" type="text" placeholder="Должность"></label>' +
        '<label><span>Номер топливной карты</span><input id="employeeFuelCard" type="text" placeholder="0000 0000"></label>' +
        '<div class="employee-form-actions"><button id="employeeCancelEdit" class="secondary-sheet-button" type="button" hidden>Отмена</button>' +
        '<button class="primary-sheet-button" type="submit">Сохранить сотрудника</button></div>' +
      '</form>' +
      '<div id="employeeResult"></div>' +
      '<div class="employee-table-wrap"><table class="employee-table"><thead><tr><th>ФИО</th><th>Отдел</th><th>Должность</th><th>Топливная карта</th><th></th></tr></thead><tbody id="employeeTableBody"></tbody></table></div>' +
      '<div class="sheet-actions employee-footer-actions"><button id="employeeBackProject" class="secondary-sheet-button" type="button">← К проекту</button></div>' +
    '</section>';

  let employees = [];
  const result = el("employeeResult");

  const resetForm = () => {
    el("employeeId").value = "";
    el("employeeFullName").value = "";
    el("employeeDepartment").value = "";
    el("employeePosition").value = "";
    el("employeeFuelCard").value = "";
    el("employeeCancelEdit").hidden = true;
  };

  const renderTable = () => {
    el("employeeCount").textContent = employees.length + " сотрудников";
    el("employeeTableBody").innerHTML = employees.length ? employees.map(employee =>
      '<tr><td><strong>' + escapeHtml(employee.full_name) + '</strong></td>' +
      '<td>' + escapeHtml(employee.department || "—") + '</td>' +
      '<td>' + escapeHtml(employee.position || "—") + '</td>' +
      '<td><code>' + escapeHtml(employee.fuel_card_number || "—") + '</code></td>' +
      '<td class="employee-row-actions"><button type="button" data-employee-edit="' + employee.id + '">Изменить</button>' +
      '<button type="button" class="danger" data-employee-delete="' + employee.id + '">Удалить</button></td></tr>'
    ).join("") : '<tr><td colspan="5"><div class="workspace-empty">Сотрудников пока нет. Добавьте первого сотрудника.</div></td></tr>';

    workspaceBody.querySelectorAll("[data-employee-edit]").forEach(button => {
      button.onclick = () => {
        const employee = employees.find(item => item.id === Number(button.dataset.employeeEdit));
        if (!employee) return;
        el("employeeId").value = employee.id;
        el("employeeFullName").value = employee.full_name || "";
        el("employeeDepartment").value = employee.department || "";
        el("employeePosition").value = employee.position || "";
        el("employeeFuelCard").value = employee.fuel_card_number || "";
        el("employeeCancelEdit").hidden = false;
        el("employeeFullName").focus();
      };
    });

    workspaceBody.querySelectorAll("[data-employee-delete]").forEach(button => {
      button.onclick = async () => {
        if (!confirm("Удалить сотрудника?")) return;
        try {
          await api("/api/projects/" + project.id + "/employees/" + button.dataset.employeeDelete, {method:"DELETE"});
          await loadEmployees();
          result.innerHTML = workspaceResult("Сотрудник удалён.", "success");
        } catch (error) {
          result.innerHTML = workspaceResult(error.message, "error");
        }
      };
    });
  };

  const loadEmployees = async () => {
    try {
      const data = await api("/api/projects/" + project.id + "/employees");
      employees = data.employees || [];
      renderTable();
    } catch (error) {
      result.innerHTML = workspaceResult(error.message, "error");
    }
  };

  el("employeeForm").onsubmit = async (event) => {
    event.preventDefault();
    const employeeId = el("employeeId").value;
    const payload = {
      full_name: el("employeeFullName").value.trim(),
      department: el("employeeDepartment").value.trim(),
      position: el("employeePosition").value.trim(),
      fuel_card_number: el("employeeFuelCard").value.trim()
    };
    try {
      await api(
        "/api/projects/" + project.id + "/employees" + (employeeId ? "/" + employeeId : ""),
        {
          method: employeeId ? "PUT" : "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify(payload)
        }
      );
      resetForm();
      await loadEmployees();
      result.innerHTML = workspaceResult(employeeId ? "Данные сотрудника обновлены." : "Сотрудник добавлен.", "success");
    } catch (error) {
      result.innerHTML = workspaceResult(error.message, "error");
    }
  };

  el("employeeCancelEdit").onclick = resetForm;
  el("employeeBackProject").onclick = () => renderProjectModule(project);
  await loadEmployees();
}


async function renderPrimavtodorBusinessModule(project, module) {
  const config = {
    counterparties: {
      title: "Контрагенты", endpoint: "counterparties", folder: "Контрагенты",
      fields: [
        ["name","Название","text"],["inn","ИНН","text"],["kpp","КПП","text"],
        ["legal_address","Юридический адрес","text"],["contact_person","Контактное лицо","text"],
        ["phone","Телефон","text"],["email","E-mail","email"]
      ]
    },
    contracts: {
      title: "Договоры", endpoint: "contracts", folder: "Договоры",
      fields: [
        ["contract_number","Номер договора","text"],["contract_date","Дата","date"],
        ["subject","Предмет договора","text"],["amount","Сумма","number"],["status","Статус","text"]
      ]
    },
    invoice_offers: {
      title: "Счёт-Оферта", endpoint: "invoice-offers", folder: "Счёт-Оферта",
      fields: [
        ["offer_number","Номер","text"],["issue_date","Дата","date"],
        ["amount","Сумма","number"],["terms","Краткие условия договора","text"],["status","Статус","text"]
      ]
    }
  }[module.module_key];
  if (!config) return;

  showWorkspaceShell("work", 'АО "Примавтодор"', config.title, "Деловой модуль проекта и связанные документы.");
  workspaceBody.innerHTML =
    '<section class="workspace-card workspace-card-wide business-module">' +
      '<div class="workspace-card-head"><div><strong>' + escapeHtml(config.title) + '</strong><small>Данные проекта АО «Примавтодор»</small></div>' +
      '<button id="businessOpenDrive" class="secondary-sheet-button" type="button">▤ Документы модуля</button></div>' +
      '<form id="businessForm" class="business-form"><input id="businessItemId" type="hidden">' +
      config.fields.map(field =>
        '<label><span>' + escapeHtml(field[1]) + '</span><input data-business-field="' + field[0] + '" type="' + field[2] + '"' +
        (["name","contract_number","offer_number"].includes(field[0]) ? ' required' : '') + '></label>'
      ).join("") +
      '<div class="business-form-actions"><button id="businessCancelEdit" class="secondary-sheet-button" type="button" hidden>Отмена</button>' +
      '<button class="primary-sheet-button" type="submit">Сохранить</button></div></form>' +
      '<div id="businessResult"></div><div id="businessList" class="business-list"></div>' +
      '<div class="sheet-actions"><button id="businessBack" class="secondary-sheet-button" type="button">← К проекту</button></div>' +
    '</section>';

  let items = [];
  let folderId = null;
  try {
    const folders = await api("/api/projects/" + project.id + "/business-folders");
    folderId = folders.folders?.[config.folder]?.id || null;
  } catch (_) {}

  const reset = () => {
    el("businessItemId").value = "";
    workspaceBody.querySelectorAll("[data-business-field]").forEach(input => input.value = "");
    el("businessCancelEdit").hidden = true;
  };

  const load = async () => {
    const data = await api("/api/projects/" + project.id + "/" + config.endpoint);
    items = data.items || [];
    el("businessList").innerHTML = items.length ? items.map(item => {
      const title = item.name || item.contract_number || item.offer_number || ("#" + item.id);
      const details = module.module_key === "counterparties"
        ? [item.inn && "ИНН " + item.inn, item.contact_person, item.phone].filter(Boolean).join(" · ")
        : [item.contract_date || item.issue_date, item.amount ? Number(item.amount).toLocaleString("ru-RU") + " ₽" : "", item.status].filter(Boolean).join(" · ");
      return '<article class="business-list-row"><div><strong>' + escapeHtml(title) + '</strong><small>' + escapeHtml(details || "Без дополнительных данных") + '</small></div>' +
        '<div><button type="button" data-business-edit="' + item.id + '">Изменить</button><button class="danger" type="button" data-business-delete="' + item.id + '">Удалить</button></div></article>';
    }).join("") : '<div class="workspace-empty">Записей пока нет.</div>';

    workspaceBody.querySelectorAll("[data-business-edit]").forEach(button => button.onclick = () => {
      const item = items.find(x => x.id === Number(button.dataset.businessEdit));
      if (!item) return;
      el("businessItemId").value = item.id;
      workspaceBody.querySelectorAll("[data-business-field]").forEach(input => input.value = item[input.dataset.businessField] ?? "");
      el("businessCancelEdit").hidden = false;
    });
    workspaceBody.querySelectorAll("[data-business-delete]").forEach(button => button.onclick = async () => {
      if (!confirm("Удалить запись?")) return;
      await api("/api/projects/" + project.id + "/" + config.endpoint + "/" + button.dataset.businessDelete, {method:"DELETE"});
      await load();
    });
  };

  el("businessForm").onsubmit = async event => {
    event.preventDefault();
    const id = el("businessItemId").value;
    const payload = {};
    workspaceBody.querySelectorAll("[data-business-field]").forEach(input => {
      payload[input.dataset.businessField] = input.type === "number" ? Number(input.value || 0) : input.value.trim();
    });
    try {
      await api("/api/projects/" + project.id + "/" + config.endpoint + (id ? "/" + id : ""), {
        method: id ? "PUT" : "POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
      });
      reset(); await load();
      el("businessResult").innerHTML = workspaceResult(id ? "Запись обновлена." : "Запись добавлена.", "success");
    } catch (error) {
      el("businessResult").innerHTML = workspaceResult(error.message, "error");
    }
  };
  el("businessCancelEdit").onclick = reset;
  el("businessBack").onclick = () => renderProjectModule(project);
  el("businessOpenDrive").onclick = () => renderDocumentsWorkspace(folderId);
  await load();
}


async function renderHomeModule(project, module) {
  const isNetwork = module.module_key === "home_network";
  const endpoint = isNetwork ? "home-devices" : "parental-controls";
  const title = isNetwork ? "Домашняя сеть" : "Детский контроль Miyori";
  const subtitle = isNetwork
    ? "Устройства домашней сети и их состояние."
    : "Прозрачные правила использования подключённого телефона ребёнка.";

  showWorkspaceShell("home", "Домашний модуль", title, subtitle);

  const fields = isNetwork ? [
    ["name","Название устройства","text"],
    ["device_type","Тип","text"],
    ["address","IP / адрес","text"],
    ["status","Статус","text"],
    ["notes","Заметка","text"]
  ] : [
    ["child_name","Имя ребёнка","text"],
    ["device_name","Телефон / устройство","text"],
    ["daily_limit_minutes","Лимит в день, минут","number"],
    ["bedtime_start","Начало ночного режима","time"],
    ["bedtime_end","Конец ночного режима","time"],
    ["blocked_categories","Ограниченные категории","text"],
    ["status","Статус","text"]
  ];

  workspaceBody.innerHTML =
    '<section class="workspace-card workspace-card-wide home-module-card">' +
      '<div class="workspace-card-head"><div><strong>' + escapeHtml(title) + '</strong><small>' + escapeHtml(subtitle) + '</small></div>' +
      '<span class="soft-status neutral">v' + escapeHtml(state.moduleVersions?.[isNetwork ? "home_network" : "parental_control"]?.version || "0.1.0") + '</span></div>' +
      (!isNetwork ? '<div class="sheet-note">Модуль не выполняет скрытое наблюдение. Управление возможно только после явной привязки мобильного устройства Miyori.</div>' : '') +
      '<form id="homeModuleForm" class="home-module-form"><input id="homeModuleItemId" type="hidden">' +
      fields.map(field =>
        '<label><span>' + escapeHtml(field[1]) + '</span><input data-home-field="' + field[0] + '" type="' + field[2] + '"' +
        (["name","child_name","device_name"].includes(field[0]) ? ' required' : '') + '></label>'
      ).join("") +
      '<div class="home-module-actions"><button id="homeModuleCancel" class="secondary-sheet-button" type="button" hidden>Отмена</button>' +
      '<button class="primary-sheet-button" type="submit">Сохранить</button></div></form>' +
      '<div id="homeModuleResult"></div><div id="homeModuleList" class="home-module-list"></div>' +
      '<div class="sheet-actions"><button id="homeModuleBack" class="secondary-sheet-button" type="button">← К проекту</button></div>' +
    '</section>';

  let items = [];
  const reset = () => {
    el("homeModuleItemId").value = "";
    workspaceBody.querySelectorAll("[data-home-field]").forEach(input => input.value = "");
    if (!isNetwork) el("homeModuleForm").querySelector('[data-home-field="daily_limit_minutes"]').value = "120";
    el("homeModuleCancel").hidden = true;
  };

  const load = async () => {
    try {
      const data = await api("/api/projects/" + project.id + "/" + endpoint);
      items = data.items || [];
      el("homeModuleList").innerHTML = items.length ? items.map(item => {
        const primary = isNetwork ? item.name : item.child_name;
        const details = isNetwork
          ? [item.device_type, item.address, item.status].filter(Boolean).join(" · ")
          : [item.device_name, (item.daily_limit_minutes || 0) + " мин/день", item.bedtime_start + "–" + item.bedtime_end, item.status].filter(Boolean).join(" · ");
        return '<article class="home-module-row"><div><strong>' + escapeHtml(primary) + '</strong><small>' + escapeHtml(details) + '</small></div>' +
          '<div><button type="button" data-home-edit="' + item.id + '">Изменить</button><button type="button" class="danger" data-home-delete="' + item.id + '">Удалить</button></div></article>';
      }).join("") : '<div class="workspace-empty">Записей пока нет.</div>';

      workspaceBody.querySelectorAll("[data-home-edit]").forEach(button => button.onclick = () => {
        const item = items.find(x => x.id === Number(button.dataset.homeEdit));
        if (!item) return;
        el("homeModuleItemId").value = item.id;
        workspaceBody.querySelectorAll("[data-home-field]").forEach(input => input.value = item[input.dataset.homeField] ?? "");
        el("homeModuleCancel").hidden = false;
      });
      workspaceBody.querySelectorAll("[data-home-delete]").forEach(button => button.onclick = async () => {
        if (!confirm("Удалить запись?")) return;
        await api("/api/projects/" + project.id + "/" + endpoint + "/" + button.dataset.homeDelete, {method:"DELETE"});
        await load();
      });
    } catch (error) {
      el("homeModuleResult").innerHTML = workspaceResult(error.message, "error");
    }
  };

  el("homeModuleForm").onsubmit = async event => {
    event.preventDefault();
    const id = el("homeModuleItemId").value;
    const payload = {};
    workspaceBody.querySelectorAll("[data-home-field]").forEach(input => {
      payload[input.dataset.homeField] = input.type === "number" ? Number(input.value || 0) : input.value.trim();
    });
    try {
      await api("/api/projects/" + project.id + "/" + endpoint + (id ? "/" + id : ""), {
        method:id ? "PUT" : "POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });
      reset();
      await load();
      el("homeModuleResult").innerHTML = workspaceResult(id ? "Запись обновлена." : "Запись добавлена.", "success");
    } catch (error) {
      el("homeModuleResult").innerHTML = workspaceResult(error.message, "error");
    }
  };
  el("homeModuleCancel").onclick = reset;
  el("homeModuleBack").onclick = () => renderProjectModule(project);
  reset();
  await load();
}


async function renderPrimavtodorSubmodule(project, module) {
  if (module.module_key === "employees") {
    await renderEmployeesModule(project, module);
    return;
  }
  if (["counterparties","contracts","invoice_offers"].includes(module.module_key)) {
    await renderPrimavtodorBusinessModule(project, module);
    return;
  }
  showWorkspaceShell(
    "work",
    'АО "Примавтодор"',
    module.name,
    "Отдельный модуль рабочего проекта."
  );

  const descriptions = {
    timesheet: "Учёт табелей, смен, рабочего времени и связанных документов.",
    garage: "Учёт гаража, техники, транспорта и эксплуатационных материалов.",
    employees: "Сотрудники проекта, кадровые сведения и связанные документы.",
    counterparties: "Организации и лица, с которыми работает проект.",
    contracts: "Договоры проекта и связанные документы.",
    invoice_offers: "Счета-оферты: счёт с краткими существенными условиями договора."
  };

  workspaceBody.innerHTML =
    '<section class="workspace-card workspace-card-wide primavtodor-module-view">' +
      '<div class="workspace-hero-icon">' +
        (module.module_key === "timesheet" ? "▦" : module.module_key === "garage" ? "▰" : module.module_key === "counterparties" ? "◎" : module.module_key === "contracts" ? "§" : module.module_key === "invoice_offers" ? "₽" : "◉") +
      '</div>' +
      '<strong>' + escapeHtml(module.name) + '</strong>' +
      '<p>' + escapeHtml(descriptions[module.module_key] || "Модуль проекта.") + '</p>' +
      '<div class="sheet-note">Модуль привязан к проекту АО «Примавтодор». Данные и документы остаются в контексте этого проекта.</div>' +
      '<div class="sheet-actions">' +
        '<button id="primavtodorModuleBack" class="secondary-sheet-button" type="button">← К проекту</button>' +
        '<button id="primavtodorModuleDocuments" class="primary-sheet-button" type="button">Документы проекта</button>' +
      '</div>' +
    '</section>';

  el("primavtodorModuleBack").onclick = () => renderProjectModule(project);
  el("primavtodorModuleDocuments").onclick = renderDocumentsWorkspace;
}

async function renderProjectModule(project) {
  state.projectId = Number(project.id);
  projectSelect.value = String(state.projectId);
  updateProjectLabel();
  showWorkspaceShell(
    project.kind === "work" ? "work" : "home",
    project.kind === "work" ? "Рабочий модуль" : "Домашний модуль",
    project.name,
    "Отдельное пространство проекта Miyori."
  );

  workspaceBody.innerHTML =
    '<div class="workspace-grid">' +
      '<section class="workspace-card"><strong>Документы</strong><small>Материалы проекта</small><div id="projectModuleDocs">Загружаю…</div></section>' +
      '<section class="workspace-card"><strong>Память</strong><small>Факты проекта</small><div id="projectModuleMemory">Загружаю…</div></section>' +
      '<section class="workspace-card"><strong>Задачи</strong><small>Фоновые процессы</small><div id="projectModuleTasks">Загружаю…</div></section>' +
      '<section id="projectSubmodulesCard" class="workspace-card workspace-card-wide" hidden>' +
        '<strong>Модули</strong><small>Разделы проекта Miyori</small>' +
        '<div id="projectSubmodules" class="workspace-project-grid"></div>' +
      '</section>' +
      '<section class="workspace-card workspace-card-wide"><div class="sheet-actions">' +
        '<button id="projectModuleDocuments" class="secondary-sheet-button" type="button">▤ Miyori Drive проекта</button>' +
        '<button id="projectModuleChat" class="primary-sheet-button" type="button">Открыть чат проекта</button>' +
      '</div></section>' +
    '</div>';

  try {
    const [docs, memory, tasks, modules] = await Promise.all([
      api("/api/projects/" + project.id + "/documents"),
      api("/api/projects/" + project.id + "/memory"),
      api("/api/projects/" + project.id + "/tasks"),
      api("/api/projects/" + project.id + "/modules")
    ]);
    el("projectModuleDocs").innerHTML = workspaceResult(
      (docs.documents || []).length + " файл(ов) · " + (docs.folders || []).length + " папок",
      "neutral"
    );
    el("projectModuleMemory").innerHTML = workspaceResult(
      (memory.facts || []).length + " фактов",
      "neutral"
    );
    el("projectModuleTasks").innerHTML = workspaceResult(
      (tasks.tasks || []).length + " задач",
      "neutral"
    );

    const projectModules = modules.modules || [];
    if (projectModules.length) {
      el("projectSubmodulesCard").hidden = false;
      el("projectSubmodules").innerHTML = projectModules.map(module => {
        const versionKey = project.kind === "work"
          ? "primavtodor_" + module.module_key
          : module.module_key;
        const meta = state.moduleVersions?.[versionKey];
        const status = meta?.status === "active" ? "Развивается" :
          meta?.status === "foundation" ? "Основа" :
          meta?.status === "planned" ? "Запланирован" : "Модуль";
        return '<button class="workspace-project-card project-submodule-card" type="button" data-module-id="' + module.id + '">' +
          '<span class="workspace-project-icon">' +
            (module.module_key === "timesheet" ? "▦" : module.module_key === "garage" ? "▰" : "◉") +
          '</span>' +
          '<strong>' + escapeHtml(module.name) + '</strong>' +
          '<small>' + escapeHtml(status) + (meta ? ' · v' + escapeHtml(meta.version) : '') + '</small>' +
        '</button>';
      }).join("");

      workspaceBody.querySelectorAll("[data-module-id]").forEach(button => {
        button.onclick = () => {
          const module = projectModules.find(item => item.id === Number(button.dataset.moduleId));
          if (!module) return;
          if (project.kind === "home" || ["home_network","parental_control"].includes(module.module_key)) {
            renderHomeModule(project, module);
          } else {
            renderPrimavtodorSubmodule(project, module);
          }
        };
      });
    }
  } catch (error) {
    workspaceBody.insertAdjacentHTML("beforeend", workspaceResult(error.message, "error"));
  }

  el("projectModuleDocuments").onclick = renderDocumentsWorkspace;
  el("projectModuleChat").onclick = async () => {
    state.conversationId = null;
    showChatWorkspace();
    showWelcome();
    await Promise.all([loadConversations(), loadMemory(), loadDocuments(), loadNexus()]);
  };
}

async function renderProjectsWorkspace(kind) {
  const isWork = kind === "work";
  showWorkspaceShell(
    kind,
    "Проекты",
    isWork ? "Рабочие проекты" : "Домашние проекты",
    isWork ? "Рабочие пространства Miyori." : "Личные и домашние пространства Miyori."
  );
  try {
    const data = await api("/api/projects");
    const projects = (data.projects || []).filter(project => (project.kind || "home") === kind);
    workspaceBody.innerHTML =
      '<section class="workspace-card workspace-card-wide"><div class="workspace-project-grid">' +
      projects.map(project =>
        '<button class="workspace-project-card ' +
        (project.name === 'АО "Примавтодор"' ? 'primavtodor-project-card' : '') +
        '" type="button" data-project-id="' + project.id + '">' +
          '<span class="workspace-project-icon">' + (isWork ? '▰' : '⌂') + '</span>' +
          '<strong>' + escapeHtml(project.name) + '</strong>' +
          '<small>' + (project.name === 'АО "Примавтодор"' ? 'Отдельный рабочий модуль' : project.name === "Личное" ? "Домашнее пространство Miyori" : 'Проект #' + project.id) + '</small>' +
        '</button>'
      ).join("") +
      '</div>' +
      (!projects.length ? '<div class="workspace-empty">Проектов в этом разделе пока нет.</div>' : '') +
      '</section>';

    workspaceBody.querySelectorAll("[data-project-id]").forEach(button => {
      button.onclick = () => {
        const project = projects.find(item => item.id === Number(button.dataset.projectId));
        if (project) renderProjectModule(project);
      };
    });
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}
