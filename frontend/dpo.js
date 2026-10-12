'use strict';
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    let key = '', offset = 0, selected = null, loadedSubject = null;
    const transitions = {
        'Recibido': ['En verificacion', 'En proceso', 'Rechazado'],
        'En verificacion': ['En proceso', 'Rechazado'],
        'En proceso': ['Completado', 'Rechazado'], 'Completado': [], 'Rechazado': [],
    };
    function message(text, failed = false) {
        $('panelStatus').textContent = text;
        $('panelStatus').dataset.state = failed ? 'error' : 'success';
    }
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
        const result = await api(`/requests/${encodeURIComponent(ticket)}`);
        selected = result.data;
        $('detailTitle').textContent = selected.ticket_id;
        $('detailText').textContent = selected.details || 'Sin detalles adicionales.';
        $('resolutionNote').value = selected.resolution_note || '';
        $('newStatus').replaceChildren();
        for (const status of transitions[selected.status]) {
            const option = document.createElement('option'); option.value = status; option.textContent = status;
            $('newStatus').append(option);
        }
        $('saveStatus').disabled = transitions[selected.status].length === 0;
        const logs = await api(`/audit-log?ticket_id=${encodeURIComponent(ticket)}`);
        $('auditEntries').textContent = JSON.stringify(logs.data, null, 2);
        $('requestDetail').classList.remove('hidden');
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
        } catch (error) { key = ''; throw error; }
    });
    $('logoutButton').onclick = () => {
        key = ''; selected = null; loadedSubject = null; offset = 0;
        $('workspace').classList.add('hidden'); $('requestDetail').classList.add('hidden');
        $('rectifyForm').classList.add('hidden'); $('logoutButton').classList.add('hidden'); $('loginForm').classList.remove('hidden');
        for (const id of ['subjectData', 'searchResults', 'auditEntries', 'detailText', 'detailTitle', 'redactResult', 'pageInfo']) $(id).textContent = '';
        for (const id of ['subjectId', 'subjectName', 'subjectEmail', 'query', 'redactText', 'redactValues', 'resolutionNote', 'apiKey']) $(id).value = '';
        $('dpoTableBody').replaceChildren(); $('newStatus').replaceChildren();
        $('portableButton').disabled = true; $('eraseButton').disabled = true;
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
        loadedSubject = null; $('portableButton').disabled = true; $('eraseButton').disabled = true;
        $('subjectData').textContent = ''; $('rectifyForm').classList.add('hidden');
        const result = await api(`/user-data?user_id=${encodeURIComponent($('subjectId').value.trim())}`);
        loadedSubject = result.data;
        $('subjectData').textContent = JSON.stringify(loadedSubject, null, 2);
        $('subjectName').value = loadedSubject.nombre || ''; $('subjectEmail').value = loadedSubject.email || '';
        $('portableButton').disabled = false; $('eraseButton').disabled = !loadedSubject.activo;
        $('rectifyForm').classList.remove('hidden');
    }
    operation($('subjectForm'), loadSubject);
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
            await loadRequests(); $('requestDetail').classList.add('hidden'); selected = null; message('Supresión completada.');
        } catch (error) { message(error.message, true); $('eraseButton').disabled = false; }
    };
    operation($('searchForm'), async () => {
        $('searchResults').textContent = '';
        const result = await api('/vector-search', { method: 'POST', body: JSON.stringify({ query: $('query').value, k: 5 }) });
        $('searchResults').textContent = JSON.stringify(result.data, null, 2);
    });
    operation($('redactForm'), async () => {
        const result = await api('/redact', { method: 'POST', body: JSON.stringify({ text: $('redactText').value,
            values: $('redactValues').value.split('\n').map(value => value.trim()).filter(Boolean) }) });
        $('redactResult').textContent = result.data.text + '\n\n' + result.data.notice;
    });
});
