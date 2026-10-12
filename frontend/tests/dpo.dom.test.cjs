const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { webcrypto } = require('node:crypto');
const { JSDOM } = require(process.env.DSAR_JSDOM_MODULE || 'jsdom');
const root = path.resolve(__dirname, '../..');
const port = 5137, base = `http://127.0.0.1:${port}`;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check) {
    for (let i = 0; i < 500; i++) { if (check()) return; await delay(10); }
    throw new Error('La interfaz no alcanzó el estado esperado.');
}
async function dom(file, source) {
    const html = fs.readFileSync(path.join(root, 'frontend', file), 'utf8');
    const instance = new JSDOM(html, { url: base, runScripts: 'outside-only' });
    const window = instance.window;
    await new Promise(resolve => window.addEventListener('load', resolve));
    window.fetch = (url, options) => fetch(new URL(url, base), options);
    window.AbortController = AbortController;
    Object.defineProperty(window.crypto, 'randomUUID', {value:()=>webcrypto.randomUUID()});
    window.confirm = () => true;
    window.URL.createObjectURL = blob => { window.downloaded = blob; return 'blob:download'; };
    window.URL.revokeObjectURL = () => {};
    window.HTMLAnchorElement.prototype.click = function () { window.downloadName = this.download; };
    window.eval(fs.readFileSync(path.join(root, 'frontend', source), 'utf8'));
    window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
    return instance;
}

test('portal y DPO usan Flask real: ticket, estados, datos, retención, PDF y sesión', async () => {
    const server = spawn(process.env.PYTHON || 'python', ['-c',
        `import sys;sys.path.insert(0,'backend');from dsar_api import create_app;app=create_app('testing');app.test_cli_runner().invoke(args=['seed-demo']);app.run(port=${port},use_reloader=False)`],
        { cwd: root, stdio: 'ignore' });
    let portal, panel;
    try {
        for (let i = 0; i < 100; i++) {
            try { if ((await fetch(base + '/api/health')).ok) break; } catch {}
            await delay(50);
        }
        assert.equal((await fetch(base + '/api/health')).status, 200);
        portal = await dom('index.html', 'main.js');
        const p = id => portal.window.document.getElementById(id);
        p('userId').value = '72839102'; p('email').value = 'juan@example.com';
        p('requestType').value = 'Acceso'; p('details').value = '<img src=x onerror=alert(1)> Juan Pérez';
        p('dsarForm').dispatchEvent(new portal.window.Event('submit', { cancelable: true }));
        await until(() => p('formStatus').dataset.state === 'success');
        const ticket = p('ticketId').textContent; assert.match(ticket, /^DSAR-[A-F0-9]{8}$/);
        panel = await dom('dpo.html', 'dpo.js'); const $ = id => panel.window.document.getElementById(id);
        const submit = id => $(id).dispatchEvent(new panel.window.Event('submit', { cancelable: true }));
        $('apiKey').value = 'invalid'; submit('loginForm');
        await until(() => $('panelStatus').dataset.state === 'error');
        assert.equal($('workspace').classList.contains('hidden'), true);
        await until(() => !$('loginButton').disabled);
        $('apiKey').value = 'test-dpo-key'; submit('loginForm');
        await until(() => !$('workspace').classList.contains('hidden'));
        assert.equal($('apiKey').value, ''); assert.match($('dpoTableBody').textContent, new RegExp(ticket));
        $('dpoTableBody').querySelector('button').click();
        await until(() => !$('requestDetail').classList.contains('hidden'));
        assert.equal($('detailText').querySelector('img'), null);
        assert.match($('detailText').textContent, /<img/);
        $('newStatus').value = 'En proceso'; submit('statusForm');
        await until(() => $('panelStatus').textContent === 'Estado actualizado.');
        await until(() => !$('saveStatus').disabled);
        $('panelStatus').textContent = ''; $('newStatus').value = 'Completado'; submit('statusForm');
        await until(() => $('panelStatus').textContent === 'Estado actualizado.');
        assert.equal($('saveStatus').disabled, true);
        $('dpoTableBody').querySelectorAll('button')[1].click();
        await until(() => panel.window.downloadName === `${ticket}.pdf`);
        assert.ok(panel.window.downloaded.size > 1000);
        $('subjectId').value = '72839102'; submit('subjectForm');
        await until(() => !$('portableButton').disabled);
        assert.match($('subjectData').textContent, /Juan Pérez/);
        $('subjectName').value = 'Juan Rectificado'; submit('rectifyForm');
        await until(() => $('subjectData').textContent.includes('Juan Rectificado'));
        $('portableButton').click(); await until(() => panel.window.downloadName === 'datos-portables.json');
        assert.match(await panel.window.downloaded.text(), /Juan Rectificado/);
        $('redactText').value = 'Juan Pérez 72839102 juan@example.com'; $('redactValues').value = 'Juan Pérez'; submit('redactForm');
        await until(() => $('redactResult').textContent.includes('[DATO OCULTO]'));
        assert.ok(!$('redactResult').textContent.includes('72839102'));
        $('subjectId').value = '45120987'; submit('subjectForm');
        await until(() => $('subjectData').textContent.includes('María Quispe'));
        $('eraseButton').click(); await until(() => $('panelStatus').textContent.includes('retención'));
        assert.equal($('eraseButton').disabled, false);
        $('subjectId').value = '72839102'; submit('subjectForm'); await until(() => $('subjectData').textContent.includes('Juan Rectificado'));
        $('eraseButton').click(); await until(() => $('panelStatus').textContent === 'Supresión completada.');
        assert.equal($('portableButton').disabled, true);
        assert.match($('dpoTableBody').textContent, /ANON-/);
        $('logoutButton').click(); assert.equal($('workspace').classList.contains('hidden'), true);
        assert.equal($('subjectData').textContent, ''); assert.equal($('dpoTableBody').textContent, '');
    } finally { portal?.window.close(); panel?.window.close(); server.kill('SIGTERM'); }
});
