'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const dsarForm = document.getElementById('dsarForm');
    const responseCard = document.getElementById('responseCard');
    const ticketIdSpan = document.getElementById('ticketId');
    const btnSubmit = document.getElementById('btnSubmit');
    const status = document.getElementById('formStatus');
    if (!dsarForm || !responseCard || !ticketIdSpan || !btnSubmit || !status) return;

    const webhookUrl = dsarForm.dataset.webhookUrl || '/api/intake';
    let sending = false;
    let lastPayload = null;
    let submissionKey = null;

    dsarForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (sending) return;
        for (const id of ['userId', 'email', 'details']) {
            const input = document.getElementById(id);
            input.value = input.value.trim();
        }
        if (!dsarForm.reportValidity()) return;

        const payload = {
            user_id: document.getElementById('userId').value,
            email: document.getElementById('email').value,
            request_type: document.getElementById('requestType').value,
            details: document.getElementById('details').value,
            timestamp: new Date().toISOString(),
        };
        const signature = JSON.stringify({ ...payload, timestamp: undefined });
        if (signature !== lastPayload) {
            submissionKey = typeof crypto.randomUUID === 'function' ? crypto.randomUUID()
                : Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, '0')).join('');
            lastPayload = signature;
        }
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        const buttonText = btnSubmit.textContent;
        sending = true;
        btnSubmit.disabled = true;
        btnSubmit.textContent = 'Enviando solicitud al agente...';
        responseCard.classList.add('hidden');
        ticketIdSpan.textContent = '';
        status.dataset.state = 'pending';
        status.textContent = 'Enviando solicitud…';

        try {
            const response = await fetch(webhookUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Idempotency-Key': submissionKey },
                body: JSON.stringify(payload),
                signal: controller.signal,
            });
            let result;
            try {
                result = await response.json();
            } catch (error) {
                if (error.name === 'AbortError') throw error;
                throw new Error(`El servidor no devolvió JSON válido (HTTP ${response.status}). Reintenta sin cambiar el formulario.`);
            }
            if (!response.ok) {
                throw new Error(result?.error?.message || `El servidor respondió HTTP ${response.status}.`);
            }
            if (!result || result.status === 'error' ||
                typeof result.ticket_id !== 'string' || !result.ticket_id.trim()) {
                throw new Error('El servidor no confirmó un ticket. Reintenta sin cambiar el formulario.');
            }
            ticketIdSpan.textContent = result.ticket_id;
            dsarForm.classList.add('hidden');
            responseCard.classList.remove('hidden');
            status.dataset.state = 'success';
            status.textContent = 'Solicitud registrada correctamente.';
        } catch (error) {
            status.dataset.state = 'error';
            if (error.name === 'AbortError') {
                status.textContent = 'La respuesta tardó demasiado. Reintenta sin cambiar el formulario para conservar el mismo ticket.';
            } else if (error instanceof TypeError) {
                status.textContent = 'No se pudo conectar con el servidor. Abre el portal desde Flask y revisa la conexión; si usas otro origen, revisa CORS.';
            } else {
                status.textContent = error.message;
            }
        } finally {
            clearTimeout(timeout);
            sending = false;
            btnSubmit.disabled = false;
            btnSubmit.textContent = buttonText;
        }
    });
});
