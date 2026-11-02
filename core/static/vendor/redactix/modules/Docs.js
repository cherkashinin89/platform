import Module from '../core/Module.js';
import Icons from '../ui/Icons.js';

/**
 * Docs module (W60): блок «Документы плитками».
 *
 * Разметка:
 *   <figure class="redactix-docs">
 *     <div class="redactix-docs-grid">
 *       <a class="redactix-doc-card" href="/view/<id>" data-file-id="<id>">
 *         <span class="redactix-doc-icon"><i class="bi bi-file-earmark-pdf"></i></span>
 *         <span class="redactix-doc-name">Отчёт.pdf</span>
 *         <span class="redactix-doc-size">2.4 МБ</span>
 *       </a>
 *     </div>
 *   </figure>
 */
export default class Docs extends Module {
    constructor(instance) {
        super(instance);
        this.liteMode = instance.config.liteMode || false;
        this.uploadUrl = instance.config.uploadUrl || null;
        this.browseUrl = instance.config.browseUrl || null;
    }

    init() {
        // Клик на карточку — открытие (редактирование списка)
        this.instance.editorEl.addEventListener('click', (e) => {
            const card = e.target.closest && e.target.closest('figure.redactix-docs');
            if (!card) return;
            // В редакторе клик по карточке открывает модалку редактирования
            if (!this.liteMode) {
                e.preventDefault();
                this.openModal(card);
            }
        });
    }

    getButtons() {
        if (this.liteMode) return [];
        return [
            {
                name: 'docs',
                label: 'Документы',
                icon: Icons.file,
                title: 'Вставить документы',
                action: () => this.openModal(),
            }
        ];
    }

    // Документы: по расширению
    isDocName(name) {
        const ext = (name || '').split('.').pop().toLowerCase();
        return ['pdf','txt','doc','docx','xls','xlsx','ppt','pptx','zip','rar','7z','tar','gz'].includes(ext);
    }

    iconForDoc(name) {
        const ext = (name || '').split('.').pop().toLowerCase();
        if (ext === 'pdf') return 'bi-file-earmark-pdf';
        if (['doc','docx'].includes(ext)) return 'bi-file-earmark-word';
        if (['xls','xlsx'].includes(ext)) return 'bi-file-earmark-excel';
        if (['ppt','pptx'].includes(ext)) return 'bi-file-earmark-ppt';
        if (['zip','rar','7z','tar','gz'].includes(ext)) return 'bi-file-earmark-zip';
        return 'bi-file-earmark-text';
    }

    humanSize(bytes) {
        const n = Number(bytes) || 0;
        if (n < 1024) return n + ' Б';
        if (n < 1024*1024) return (n/1024).toFixed(1) + ' КБ';
        if (n < 1024*1024*1024) return (n/1024/1024).toFixed(1) + ' МБ';
        return (n/1024/1024/1024).toFixed(1) + ' ГБ';
    }

    openModal(existingFigure = null) {
        if (this.liteMode) return;
        // Прямо открываем эксплорер облака (W58)
        if (typeof window.fmOpen !== 'function') {
            alert('Модалка облака недоступна');
            return;
        }
        const folderEl = document.getElementById('redactix-folder-id');
        const startFolder = folderEl ? parseInt(folderEl.value, 10) || null : null;
        window.fmOpen(async (files) => {
            const ctxQuery = (this.uploadUrl.split('?')[1]) || '';
            const items = [];
            for (const f of files) {
                try {
                    const fd = new FormData();
                    fd.append('file_id', f.id);
                    const r = await fetch('/admin/redactix/copy?' + ctxQuery, { method: 'POST', body: fd });
                    const data = await r.json();
                    if (data.success) {
                        items.push({ name: data.name, size: this.humanSize(data.size), src: data.src });
                    }
                } catch (e) {}
            }
            if (items.length) {
                this.insertFigure(items);
            }
            this.instance.sync();
        }, startFolder);
    }

    readFigure(figure) {
        const items = [];
        figure.querySelectorAll('.redactix-doc-card').forEach(a => {
            const name = a.querySelector('.redactix-doc-name')?.textContent || '';
            const sizeText = a.querySelector('.redactix-doc-size')?.textContent || '0';
            const src = a.getAttribute('href') || '';
            items.push({ name, size: sizeText, src });
        });
        return items;
    }

    insertFigure(items) {
        const figure = document.createElement('figure');
        figure.className = 'redactix-docs';
        const grid = document.createElement('div');
        grid.className = 'redactix-docs-grid';
        items.forEach(it => {
            const a = document.createElement('a');
            a.className = 'redactix-doc-card';
            const fid = (it.src || '').replace(/[^0-9]/g, '');
            const ext = (it.name || '').split('.').pop().toLowerCase();
            const isOffice = ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'].includes(ext);
            a.setAttribute('href', fid ? (isOffice ? '/view/' + fid : '/files/' + fid) : '#');
            a.setAttribute('data-file-id', fid);
            let iconClass = 'redactix-doc-icon';
            if (['pdf'].includes(ext)) iconClass += ' doc-pdf';
            else if (['doc','docx'].includes(ext)) iconClass += ' doc-word';
            else if (['xls','xlsx'].includes(ext)) iconClass += ' doc-excel';
            else if (['ppt','pptx'].includes(ext)) iconClass += ' doc-ppt';
            else if (['zip','rar','7z','tar','gz'].includes(ext)) iconClass += ' doc-archive';
            a.innerHTML = '<span class="' + iconClass + '"><i class="bi ' + this.iconForDoc(it.name) + '"></i></span>' +
                '<span class="redactix-doc-name">' + (it.name || '') + '</span>' +
                '<span class="redactix-doc-size">' + (it.size || '') + '</span>';
            grid.appendChild(a);
        });
        figure.appendChild(grid);
        const editorEl = this.instance.editorEl;
        const lastBlock = editorEl.lastElementChild;
        if (lastBlock) lastBlock.after(figure); else editorEl.appendChild(figure);
    }

    insertEmpty() {
        this.openModal();
    }
}
