/* =======================================================
   SARI AI Web App Controller (Guru & Siswa)
   ======================================================= */

/* -------------------------------------------------------
   🧩 Utility Functions
---------------------------------------------------------- */
async function fetchJSON(url, options = {}) {
    try {
        const res = await fetch(url, options);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        alert(`❌ Gagal memuat data: ${err.message}`);
        throw err;
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
    alert("📋 ID berhasil disalin!");
}

/* -------------------------------------------------------
   👩‍🏫 TEACHER PANEL
---------------------------------------------------------- */
const TeacherApp = {
    showTab(tabName, event) {
        document.querySelectorAll('.tab').forEach(t => t.style.display = 'none');
        document.getElementById(tabName).style.display = 'block';

        document.querySelectorAll('.sidebar li').forEach(li => li.classList.remove('active'));
        if (event) event.target.classList.add('active');

        if (tabName === 'list') TeacherApp.loadList();
    },

    async generate() {
        const theme = document.getElementById('theme').value.trim();
        const level = document.getElementById('level').value;
        if (!theme) return alert("⚠️ Tema wajib diisi!");

        const resultEl = document.getElementById('result');
        resultEl.innerHTML = `<p>⏳ Sedang membuat LKPD dengan AI...</p>`;

        try {
            const data = await fetchJSON('/api/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme, level})
            });

            resultEl.innerHTML = `
                <div class="alert success">
                    <p><strong>ID:</strong> <code>${data.id}</code></p>
                    <div class="actions">
                        <button class="btn btn-success" onclick="copyToClipboard('${data.id}')">Copy</button>
                        <button class="btn btn-primary" onclick="TeacherApp.openStudent('${data.id}')">Lihat LKPD</button>
                    </div>
                </div>`;
        } catch {
            resultEl.innerHTML = `<div class="alert error">❌ Gagal membuat LKPD. Coba lagi.</div>`;
        }
    },

    openStudent(id) {
        window.open(`/student.html?id=${id}`, '_blank');
    },

    async loadRekap() {
        const id = document.getElementById('rekap-id').value.trim();
        if (!id) return alert("Masukkan ID LKPD!");

        const rekapEl = document.getElementById('rekap-table');
        rekapEl.innerHTML = `<p>⏳ Memuat data...</p>`;

        const data = await fetchJSON(`/api/answers/${id}`);
        if (!Array.isArray(data) || data.length === 0) {
            rekapEl.innerHTML = `<p>Belum ada jawaban siswa.</p>`;
            document.getElementById('export-buttons').style.display = 'none';
            return;
        }

        let html = `
            <table class="table">
                <tr>
                    <th>Nama</th>
                    <th>Nilai</th>
                    <th>Status</th>
                    <th>Jumlah Soal</th>
                </tr>`;

        data.forEach(r => {
            const statusClass = r.status === 'Tinggi' ? 'status-tinggi'
                : r.status === 'Cukup' ? 'status-cukup'
                : 'status-bimbingan';
            html += `
                <tr>
                    <td>${r.name}</td>
                    <td>${r.avg}</td>
                    <td class="${statusClass}">${r.status}</td>
                    <td>${r.total_questions}</td>
                </tr>`;
        });

        html += `</table>`;
        rekapEl.innerHTML = html;
        document.getElementById('export-buttons').style.display = 'block';
        window.currentId = id;
    },

    downloadCSV() {
        if (!window.currentId) return alert("⚠️ Lihat rekap dulu!");
        window.location.href = `/api/export/${window.currentId}`;
    },

    downloadXLSX() {
        if (!window.currentId) return alert("⚠️ Lihat rekap dulu!");
        window.location.href = `/api/export-xlsx/${window.currentId}`;
    },

    async loadList() {
        const listEl = document.getElementById('lkpd-list');
        listEl.innerHTML = `<p>⏳ Memuat daftar LKPD...</p>`;

        const data = await fetchJSON('/api/all-ids');
        if (!data.ids || data.ids.length === 0) {
            listEl.innerHTML = `<p>Belum ada LKPD.</p>`;
            return;
        }

        let html = '';
        data.ids.forEach(id => {
            html += `
                <div class="card">
                    <strong>ID: ${id}</strong>
                    <button class="btn btn-primary" onclick="TeacherApp.openStudent('${id}')">Lihat</button>
                </div>`;
        });
        listEl.innerHTML = html;
    }
};

/* -------------------------------------------------------
   🧒 STUDENT PANEL
---------------------------------------------------------- */
const StudentApp = {
    currentLKPD: null,

    async loadLKPD() {
        const id = document.getElementById('lkpd-id').value.trim();
        const nama = document.getElementById('nama').value.trim();
        if (!id || !nama) return alert("⚠️ ID LKPD dan Nama wajib diisi!");

        const lkpd = await fetchJSON(`/api/lkpd/${id}`);
        StudentApp.currentLKPD = {...lkpd, id, nama};

        document.getElementById('judul-lkpd').textContent = lkpd.title;
        document.getElementById('tema').textContent = lkpd.theme;
        document.getElementById('tingkat').textContent = lkpd.difficulty;

        const form = document.getElementById('jawaban-form');
        form.innerHTML = '';
        lkpd.questions.forEach((q, i) => {
            const div = document.createElement('div');
            div.className = 'question-card';
            div.innerHTML = `
                <h4>${i + 1}. [${q.type}] ${q.question}</h4>
                ${q.type === 'PG' ? StudentApp.renderPG(q) : StudentApp.renderEsai(q)}
            `;
            form.appendChild(div);
        });

        document.getElementById('form-section').style.display = 'none';
        document.getElementById('lkpd-content').style.display = 'block';
    },

    renderPG(q) {
        return Object.keys(q.options).map(key => `
            <label class="radio-option">
                <input type="radio" name="q${q.id}" value="${key}" required>
                <span>${key}. ${q.options[key]}</span>
            </label>
        `).join('');
    },

    renderEsai(q) {
        return `
            <textarea name="q${q.id}" placeholder="Tulis jawaban di sini..." required></textarea>
        `;
    },

    async submitJawaban() {
        if (!confirm("Yakin ingin mengumpulkan jawaban?")) return;

        const form = document.getElementById('jawaban-form');
        const formData = new FormData(form);
        const answers = [];

        StudentApp.currentLKPD.questions.forEach(q => {
            const input = formData.get(`q${q.id}`);
            answers.push({
                id: q.id,
                type: q.type,
                question: q.question,
                jawaban: input || "",
                kunci: q.answer,
                bobot: q.score
            });
        });

        await fetchJSON('/api/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                lkpd_id: StudentApp.currentLKPD.id,
                name: StudentApp.currentL
