const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../main.js'), 'utf8');

function classList(initial = []) {
    const values = new Set(initial);
    return { add: (value) => values.add(value), remove: (value) => values.delete(value),
             contains: (value) => values.has(value) };
}

function setup(fetch, valid = true) {
    const button = { disabled: false, textContent: 'Enviar' };
    const status = { textContent: '', dataset: {} };
    const ticket = { textContent: '' };
    const card = { classList: classList(['hidden']) };
    const inputs = {
        userId: { value: ' 72839102 ' }, email: { value: ' demo@example.invalid ' },
        requestType: { value: 'Acceso' }, details: { value: ' Mis datos ' },
    };
    const form = {
        dataset: {}, classList: classList(), reportValidity: () => valid,
        addEventListener(event, handler) { this.handler = handler; },
    };
    const elements = { dsarForm: form, responseCard: card, ticketId: ticket,
                       btnSubmit: button, formStatus: status, ...inputs };
    vm.runInNewContext(source, {
        document: { getElementById: (id) => elements[id],
                    addEventListener: (event, callback) => callback() },
        fetch, AbortController, setTimeout, clearTimeout, TypeError, crypto: require("node:crypto").webcrypto,
    });
    return { form, button, status, ticket, card, inputs,
             submit: () => form.handler({ preventDefault() {} }) };
}

test('envía el contrato existente y confirma únicamente el ticket real', async () => {
    let sent;
    const ui = setup(async (url, options) => {
        sent = { url, options };
        return { ok: true, json: async () => ({ status: 'success', ticket_id: 'DSAR-001' }) };
    });
    await ui.submit();
    assert.equal(sent.url, '/api/intake');
    assert.equal(sent.options.method, 'POST');
    assert.equal(sent.options.headers['Content-Type'], 'application/json');
    const payload = JSON.parse(sent.options.body);
    assert.equal(payload.user_id, '72839102');
    assert.equal(payload.email, 'demo@example.invalid');
    assert.equal(payload.request_type, 'Acceso');
    assert.equal(payload.details, 'Mis datos');
    assert.ok(!Number.isNaN(Date.parse(payload.timestamp)));
    assert.equal(ui.ticket.textContent, 'DSAR-001');
    assert.equal(ui.form.classList.contains('hidden'), true);
    assert.equal(ui.card.classList.contains('hidden'), false);
    assert.equal(ui.button.disabled, false);
});

test('no muestra éxito ni tickets ficticios ante errores', async () => {
    const scenarios = [
        [async () => ({ ok: false, status: 500, json: async () => ({}) }), /HTTP 500/],
        [async () => { throw new TypeError('Failed to fetch'); }, /CORS/],
        [async () => ({ ok: true, json: async () => { throw new SyntaxError(); } }), /JSON válido/],
        [async () => ({ ok: true, json: async () => ({}) }), /ticket/],
        [async () => ({ ok: true, json: async () => ({ status: 'error', ticket_id: 'DSAR-X' }) }), /ticket/],
        [async () => { const error = new Error(); error.name = 'AbortError'; throw error; }, /tardó demasiado/],
    ];
    for (const [fetch, expected] of scenarios) {
        const ui = setup(fetch);
        await ui.submit();
        assert.match(ui.status.textContent, expected);
        assert.equal(ui.status.dataset.state, 'error');
        assert.equal(ui.form.classList.contains('hidden'), false);
        assert.equal(ui.card.classList.contains('hidden'), true);
        assert.equal(ui.ticket.textContent, '');
        assert.equal(ui.inputs.userId.value, '72839102');
        assert.equal(ui.button.disabled, false);
        assert.equal(ui.button.textContent, 'Enviar');
    }
});

test('no envía campos inválidos', async () => {
    let calls = 0;
    const ui = setup(async () => { calls++; }, false);
    await ui.submit();
    assert.equal(calls, 0);
});

test('evita envíos simultáneos', async () => {
    let calls = 0;
    let finish;
    const ui = setup(() => {
        calls++;
        return new Promise((resolve) => { finish = resolve; });
    });
    const pending = ui.submit();
    assert.equal(ui.button.disabled, true);
    await ui.submit();
    assert.equal(calls, 1);
    finish({ ok: true, json: async () => ({ ticket_id: 'DSAR-002' }) });
    await pending;
    assert.equal(ui.button.disabled, false);
});


test('reutiliza la clave después de un fallo y cambia al editar campos', async () => {
    const keys = [];
    const ui = setup(async (url, options) => {
        keys.push(options.headers['Idempotency-Key']);
        throw new TypeError('offline');
    });
    await ui.submit(); await ui.submit();
    assert.equal(keys[0], keys[1]);
    assert.match(keys[0], /^[a-f0-9-]{36}$/);
    ui.inputs.details.value = 'Otra solicitud';
    await ui.submit(); assert.notEqual(keys[1], keys[2]);
});

test('muestra el diagnóstico del backend y conserva los datos', async () => {
    const ui = setup(async () => ({ok:false, status:503, json:async () => ({status:'error',error:{message:'No se pudo conectar con n8n.'}})}));
    await ui.submit();
    assert.equal(ui.status.textContent, 'No se pudo conectar con n8n.');
    assert.equal(ui.form.classList.contains('hidden'), false);
});
