'use strict';
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    let key = '', offset = 0, selected = null, loadedSubject = null;
    let reviewVersion = 0;
    const transitions = {
        'Recibido': ['En verificacion', 'En proceso', 'Rechazado'],
        'En verificacion': ['En proceso', 'Rechazado'],
        'En proceso': ['Completado', 'Rechazado'], 'Completado': [], 'Rechazado': [],
    };
    function message(text, failed = false) {
        $('panelStatus').textContent = text;
        $('panelStatus').dataset.state = failed ? 'error' : 'success';
    }
    function showPanel(id) {
        document.querySelectorAll('.panel-section').forEach(panel => panel.classList.toggle('hidden', panel.id !== id));
        document.querySelectorAll('[data-panel]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.panel === id)));
        $(id).scrollIntoView?.({behavior: 'smooth', block: 'start'});
    }
    document.querySelectorAll('[data-panel]').forEach(button => { button.onclick = () => showPanel(button.dataset.panel); });
    const guide = {
        Acceso: 'Consulta los datos registrados y usa la IA para localizar documentos. Revisa los fragmentos antes de entregar información.',
        Portabilidad: 'Consulta los datos y descarga el JSON portable. La IA te ayuda a localizar documentos adicionales para revisar.',
        Rectificacion: 'Comprueba los datos actuales del titular y guarda la corrección autorizada en Datos del titular.',
        Supresion: 'Revisa la identidad, los datos y los documentos relacionados. La supresión de la base respeta los bloqueos de retención; los documentos se tratan aparte.',
    };
    function field(container, name, value) {
        const term = document.createElement('dt'), description = document.createElement('dd');
        term.textContent = name; description.textContent = value ?? 'Sin dato'; container.append(term, description);
    }
    async function checkAI() {
        $('aiStatus').textContent = 'Comprobando modelo e índice local…';
        $('aiStatus').dataset.state = 'pending';
        try {
            const result = await api('/ai/status');
            $('aiStatus').textContent = result.data.ready
                ? `IA lista · ${result.data.documents} documentos · ${result.data.chunks} fragmentos`
                : result.data.message;
            $('aiStatus').dataset.state = result.data.ready ? 'success' : 'error';
        } catch (error) {
            if (!key) return;
            $('aiStatus').textContent = 'No se pudo comprobar la IA. Inicia el proyecto con iniciar.py y vuelve a comprobar.';
            $('aiStatus').dataset.state = 'error';
        }
    }
    $('refreshAI').onclick = checkAI;
    async function api(path, options = {}) {
        const sessionKey = key;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 30000);
        try {
            const response = await fetch(`/api${path}`, { ...options, signal: controller.signal,
                headers: { 'Content-Type': 'application/json', 'X-API-Key': key, ...options.headers } });
            if (options.pdf && response.ok) {
                const blob = await response.blob();
                if (!key || key !== sessionKey) throw new Error("La sesión terminó.");
                return blob;
            }
            const result = await response.json();
            if (!key || key !== sessionKey) throw new Error("La sesión terminó.");
            if (!response.ok) throw new Error(result.error?.message || `Error HTTP ${response.status}`);
            return result;
        } finally { clearTimeout(timer); }
    }
    function operation(form, action) {
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const buttons = Array.from(form.querySelectorAll('button'));
            const states = buttons.map(button => button.disabled);
            if (buttons.some(button => button.disabled)) return;
            buttons.forEach(button => { button.disabled = true; });
            try { await action(); }
            catch (error) { message(error.name === 'AbortError' ? 'La consulta tardó demasiado.' : error.message, true); }
            finally { buttons.forEach((button, index) => { button.disabled = states[index] || (button.id === "saveStatus" && selected && transitions[selected.status].length === 0); }); }
        });
    }
    function download(blob, name) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a'); link.href = url; link.download = name; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    async function detail(ticket) {
        const version = ++reviewVersion;
        const result = await api(`/requests/${encodeURIComponent(ticket)}`);
        if (version !== reviewVersion) return;
        selected = result.data;
        $('detailTitle').textContent = selected.ticket_id;
        $('caseSummary').textContent = `${selected.request_type} · Documento ${selected.user_id} · ${selected.status}`;
        $('caseGuide').textContent = guide[selected.request_type];
        $('subjectId').value = selected.user_id;
        $('query').value = 'datos de contacto, información personal y solicitudes';
        $('scopeSubject').disabled = false; $('scopeSubject').checked = true;
        $('aiCase').textContent = `Solicitud ${selected.ticket_id} · ${selected.request_type} · Titular ${selected.user_id}`;
        $('searchResults').replaceChildren(); $('searchNotice').textContent = '';
        $('detailText').textContent = selected.details || 'Sin detalles adicionales.';
        $('resolutionNote').value = selected.resolution_note || '';
        $('newStatus').replaceChildren();
        for (const status of transitions[selected.status]) {
            const option = document.createElement('option'); option.value = status; option.textContent = status;
            $('newStatus').append(option);
        }
        $('saveStatus').disabled = transitions[selected.status].length === 0;
        const logs = await api(`/audit-log?ticket_id=${encodeURIComponent(ticket)}`);
        if (version !== reviewVersion) return;
        $('auditEntries').replaceChildren();
        const actions = {REQUEST_CREATED: 'Solicitud registrada', REQUEST_STATUS_CHANGE: 'Estado actualizado',
            USER_DATA_ACCESS: 'Datos consultados', USER_DATA_PORTABILITY: 'Datos descargados',
            USER_RECTIFIED: 'Datos rectificados', USER_ERASURE: 'Supresión solicitada'};
        for (const log of logs.data) {
            const entry = document.createElement('p');
            entry.textContent = `${new Date(log.timestamp).toLocaleString()} · ${actions[log.action] || log.action} · ${log.outcome === 'success' ? 'Completado' : log.outcome === 'denied' ? 'Denegado' : log.outcome}`;
            $('auditEntries').append(entry);
        }
        $('requestDetail').classList.remove('hidden');
        $('requestDetail').scrollIntoView?.({behavior: 'smooth', block: 'start'});
        try { await loadSubject(); }
        catch (error) { if (version === reviewVersion) $('subjectData').textContent = error.message; }
    }
    async function loadRequests() {
        const params = new URLSearchParams({ limit: '20', offset: String(offset) });
        if ($('statusFilter').value) params.set('status', $('statusFilter').value);
        if ($('typeFilter').value) params.set('request_type', $('typeFilter').value);
        const result = await api(`/requests?${params}`);
        $('dpoTableBody').replaceChildren();
        for (const item of result.data) {
            const row = document.createElement('tr');
            for (const value of [item.ticket_id, item.user_id, item.request_type, item.status,
                item.sla_days_remaining === null ? 'Cerrado' : `${item.sla_days_remaining} días`]) {
                const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
            }
            const actions = document.createElement('td');
            const open = document.createElement('button'); open.textContent = 'Revisar'; open.type = 'button';
            open.onclick = () => detail(item.ticket_id).catch(error => message(error.message, true));
            const pdf = document.createElement('button'); pdf.textContent = 'PDF'; pdf.type = 'button';
            pdf.onclick = async () => {
                pdf.disabled = true;
                try { download(await api(`/requests/${encodeURIComponent(item.ticket_id)}/report.pdf`, { pdf: true }), `${item.ticket_id}.pdf`); }
                catch (error) { message(error.message, true); } finally { pdf.disabled = false; }
            };
            actions.append(open, pdf); row.append(actions); $('dpoTableBody').append(row);
        }
        if (!result.data.length) {
            const row = document.createElement('tr'), cell = document.createElement('td');
            cell.colSpan = 6; cell.textContent = 'No hay solicitudes para estos filtros.'; row.append(cell); $('dpoTableBody').append(row);
        }
        $('pageInfo').textContent = `${result.total} solicitudes · página ${Math.floor(offset / 20) + 1}`;
        $('previousPage').disabled = offset === 0; $('nextPage').disabled = offset + 20 >= result.total;
    }
    operation($('loginForm'), async () => {
        key = $('apiKey').value.trim();
        try {
            await api('/audit-log?limit=1');
            await loadRequests();
            $('apiKey').value = ''; $('loginForm').classList.add('hidden');
            $('logoutButton').classList.remove('hidden'); $('workspace').classList.remove('hidden');
            message('Conectado al backend.');
            showPanel('requestsPanel'); checkAI();
        } catch (error) { key = ''; throw error; }
    });
    $('logoutButton').onclick = () => {
        key = ''; selected = null; loadedSubject = null; offset = 0; reviewVersion++;
        $('workspace').classList.add('hidden'); $('requestDetail').classList.add('hidden');
        $('rectifyForm').classList.add('hidden'); $('logoutButton').classList.add('hidden'); $('loginForm').classList.remove('hidden');
        for (const id of ['subjectData', 'searchResults', 'auditEntries', 'detailText', 'detailTitle', 'redactResult', 'pageInfo',
                         'caseSummary', 'caseGuide', 'aiCase', 'aiStatus', 'searchNotice']) $(id).textContent = '';
        for (const id of ['subjectId', 'subjectName', 'subjectEmail', 'query', 'redactText', 'redactValues', 'resolutionNote', 'apiKey']) $(id).value = '';
        $('dpoTableBody').replaceChildren(); $('newStatus').replaceChildren();
        $('portableButton').disabled = true; $('eraseButton').disabled = true;
        $('scopeSubject').checked = false; $('scopeSubject').disabled = true;
        message('Sesión cerrada.');
    };
    operation($('filterForm'), async () => { offset = 0; await loadRequests(); });
    for (const [id, step] of [['previousPage', -20], ['nextPage', 20]]) $(id).onclick = async () => {
        $(id).disabled = true; offset = Math.max(0, offset + step);
        try { await loadRequests(); } catch (error) { offset = Math.max(0, offset - step); message(error.message, true); $(id).disabled = false; }
    };
    operation($('statusForm'), async () => {
        if (!selected) return;
        const ticket = selected.ticket_id;
        await api(`/requests/${encodeURIComponent(ticket)}/status`, { method: 'PATCH', body: JSON.stringify({
            status: $('newStatus').value, resolution_note: $('resolutionNote').value }) });
        await detail(ticket); await loadRequests(); message('Estado actualizado.');
    });
    async function loadSubject() {
        const documentId = $('subjectId').value.trim();
        loadedSubject = null; $('portableButton').disabled = true; $('eraseButton').disabled = true;
        $('subjectData').textContent = ''; $('rectifyForm').classList.add('hidden');
        const result = await api(`/user-data?user_id=${encodeURIComponent(documentId)}`);
        if (documentId !== $('subjectId').value.trim()) return;
        loadedSubject = result.data;
        $('subjectData').replaceChildren();
        const summary = document.createElement('dl'); summary.className = 'data-summary';
        field(summary, 'Nombre', loadedSubject.nombre); field(summary, 'Documento', loadedSubject.document_id);
        field(summary, 'Correo', loadedSubject.email); field(summary, 'Estado', loadedSubject.activo ? 'Activo' : 'Anonimizado');
        field(summary, 'Solicitudes vinculadas', String(loadedSubject.solicitudes?.length || 0));
        $('subjectData').append(summary);
        $('subjectName').value = loadedSubject.nombre || ''; $('subjectEmail').value = loadedSubject.email || '';
        $('portableButton').disabled = false; $('eraseButton').disabled = !loadedSubject.activo;
        $('rectifyForm').classList.remove('hidden');
    }
    operation($('subjectForm'), loadSubject);
    $('caseSubject').onclick = () => showPanel('subjectPanel');
    $('caseAI').onclick = () => { showPanel('aiPanel'); $('searchForm').requestSubmit(); };
    $('portableButton').onclick = async () => {
        if (!loadedSubject) return;
        try {
            const result = await api(`/user-data?user_id=${encodeURIComponent(loadedSubject.document_id)}&format=portable`);
            download(new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' }), 'datos-portables.json');
        } catch (error) { message(error.message, true); }
    };
    operation($('rectifyForm'), async () => {
        if (!loadedSubject) return;
        const changes = {}; if ($('subjectName').value !== (loadedSubject.nombre || '')) changes.nombre = $('subjectName').value;
        if ($('subjectEmail').value !== (loadedSubject.email || '')) changes.email = $('subjectEmail').value;
        if (!Object.keys(changes).length) return message('No hay cambios.');
        await api('/rectify-user', { method: 'PATCH', body: JSON.stringify({ user_id: loadedSubject.document_id, changes }) });
        await loadSubject(); message('Datos rectificados.');
    });
    $('eraseButton').onclick = async () => {
        if (!loadedSubject || !confirm('¿Verificaste la identidad y autorizas anonimizar los datos del titular? Esta acción no se puede deshacer.')) return;
        $('eraseButton').disabled = true;
        try {
            await api('/delete-user', { method: 'POST', body: JSON.stringify({ user_id: loadedSubject.document_id }) });
            loadedSubject = null; $('subjectData').textContent = 'Titular anonimizado.';
            $('rectifyForm').classList.add('hidden'); $('portableButton').disabled = true;
            $('subjectName').value = ''; $('subjectEmail').value = '';
            await loadRequests(); $('requestDetail').classList.add('hidden'); selected = null; reviewVersion++;
            $('searchResults').replaceChildren(); $('searchNotice').textContent = ''; $('aiCase').textContent = 'Titular anonimizado. Los documentos externos requieren revisión y actualización del índice.';
            $('scopeSubject').checked = false; $('scopeSubject').disabled = true;
            $('redactText').value = ''; $('redactValues').value = ''; $('redactResult').textContent = '';
            message('Supresión completada.');
        } catch (error) { message(error.message, true); $('eraseButton').disabled = false; }
    };
    operation($('searchForm'), async () => {
        const version = reviewVersion;
        $('searchResults').replaceChildren(); $('searchNotice').textContent = 'Buscando con el modelo local…';
        const payload = {query: $('query').value, k: 5};
        if ($('scopeSubject').checked && selected) payload.user_id = selected.user_id;
        let result;
        try { result = await api('/vector-search', { method: 'POST', body: JSON.stringify(payload) }); }
        catch (error) { if (key && version === reviewVersion) $('searchNotice').textContent = 'La búsqueda no se pudo completar. Comprueba el estado de IA de arriba.'; throw error; }
        if (version !== reviewVersion) return;
        $('searchNotice').textContent = result.data.count
            ? `${result.data.count} fragmentos encontrados. Revisa su pertinencia y los datos de terceros antes de utilizarlos. La similitud mide relación temática, no certeza.`
            : payload.user_id ? 'No hay documentos indexados que mencionen este ID. Añade los documentos del titular y vuelve a iniciar para actualizar el índice.' : 'No se encontraron fragmentos.';
        for (const item of result.data.results) {
            const card = document.createElement('article'); card.className = 'search-result';
            const title = document.createElement('h3'); title.textContent = item.fuente;
            const score = document.createElement('p'); score.className = 'help'; score.textContent = `Similitud: ${Number(item.score).toFixed(3)}`;
            const text = document.createElement('p'); text.className = 'excerpt'; text.textContent = item.texto;
            const copy = document.createElement('button'); copy.type = 'button'; copy.textContent = 'Revisar y ocultar datos de este fragmento';
            copy.onclick = () => { $('redactText').value = item.texto;
                $('redactValues').value = loadedSubject?.document_id === selected?.user_id && loadedSubject?.nombre ? loadedSubject.nombre : '';
                $('redactResult').textContent = ''; $('redactText').focus(); };
            card.append(title, score, text, copy); $('searchResults').append(card);
        }
    });
    document.querySelectorAll('[data-query]').forEach(button => { button.onclick = () => {
        $('query').value = button.dataset.query; $('searchForm').requestSubmit();
    }; });
    operation($('redactForm'), async () => {
        const result = await api('/redact', { method: 'POST', body: JSON.stringify({ text: $('redactText').value,
            values: $('redactValues').value.split('\n').map(value => value.trim()).filter(Boolean) }) });
        $('redactResult').textContent = result.data.text + '\n\n' + result.data.notice;
    });
});
