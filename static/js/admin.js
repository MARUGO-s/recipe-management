// データベース管理システム JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // 要素の取得
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadStatus = document.getElementById('uploadStatus');
    const downloadBtn = document.getElementById('downloadBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    const viewDataBtn = document.getElementById('viewDataBtn');
    const exportDataBtn = document.getElementById('exportDataBtn');
    const clearDataBtn = document.getElementById('clearDataBtn');
    
    let selectedFile = null;

    // ファイルアップロード関連のイベント
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);

    // ボタンイベント
    uploadBtn.addEventListener('click', uploadFile);
    downloadBtn.addEventListener('click', downloadTemplate);
    refreshBtn.addEventListener('click', refreshDatabaseStats);
    viewDataBtn.addEventListener('click', viewDatabaseData);
    exportDataBtn.addEventListener('click', exportDatabaseData);
    clearDataBtn.addEventListener('click', clearDatabaseData);

    // 初期化
    refreshDatabaseStats();

    // ドラッグ&ドロップ処理
    function handleDragOver(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    }

    function handleDrop(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    }

    function handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    }

    function handleFile(file) {
        // CSVファイルかチェック
        if (!file.name.toLowerCase().endsWith('.csv')) {
            showStatus('error', 'CSVファイルのみアップロード可能です。');
            return;
        }

        // ファイルサイズチェック（10MB制限）
        if (file.size > 10 * 1024 * 1024) {
            showStatus('error', 'ファイルサイズは10MB以下にしてください。');
            return;
        }

        selectedFile = file;
        uploadBtn.disabled = false;
        
        // アップロードエリアの表示を更新
        uploadArea.innerHTML = `
            <i class="fas fa-file-csv fa-3x text-success mb-3"></i>
            <h5 class="text-success">${file.name}</h5>
            <p class="text-muted">ファイルサイズ: ${formatFileSize(file.size)}</p>
            <small class="text-info">クリックしてファイルを変更</small>
        `;

        showStatus('info', 'ファイルが選択されました。アップロードボタンをクリックしてください。');
    }

    // ファイルアップロード
    async function uploadFile() {
        if (!selectedFile) {
            showStatus('error', 'ファイルが選択されていません。');
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            uploadBtn.disabled = true;
            uploadProgress.style.display = 'block';
            showStatus('info', 'ファイルをアップロード中...');

            const response = await fetch('/admin/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                showStatus('success', `アップロード完了！${result.count}件のデータが登録されました。`);
                resetUploadArea();
                refreshDatabaseStats();
            } else {
                showStatus('error', result.error || 'アップロードに失敗しました。');
            }
        } catch (error) {
            showStatus('error', 'アップロード中にエラーが発生しました。');
            console.error('Upload error:', error);
        } finally {
            uploadBtn.disabled = false;
            uploadProgress.style.display = 'none';
        }
    }

    // テンプレートダウンロード
    function downloadTemplate() {
        const templateType = document.querySelector('input[name="templateType"]:checked').value;
        
        fetch(`/admin/template?type=${templateType}`)
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `cost_master_template_${templateType}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showStatus('success', 'テンプレートをダウンロードしました。');
            })
            .catch(error => {
                showStatus('error', 'テンプレートのダウンロードに失敗しました。');
                console.error('Download error:', error);
            });
    }

    // データベース統計の更新
    async function refreshDatabaseStats() {
        try {
            const response = await fetch('/admin/stats');
            const stats = await response.json();

            if (response.ok) {
                document.getElementById('totalIngredients').textContent = stats.ingredients || 0;
                document.getElementById('totalRecipes').textContent = stats.recipes || 0;
                document.getElementById('lastUpdate').textContent = stats.last_update || '-';
            }
        } catch (error) {
            console.error('Stats error:', error);
        }
    }

    // データベース内容の確認
    async function viewDatabaseData() {
        try {
            const response = await fetch('/admin/data');
            const data = await response.json();

            if (response.ok) {
                // モーダルでデータを表示
                showDataModal(data);
            } else {
                showStatus('error', 'データの取得に失敗しました。');
            }
        } catch (error) {
            showStatus('error', 'データの取得中にエラーが発生しました。');
            console.error('Data fetch error:', error);
        }
    }

    // データのエクスポート
    async function exportDatabaseData() {
        try {
            const response = await fetch('/admin/export');
            const blob = await response.blob();
            
            if (response.ok) {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `cost_master_export_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showStatus('success', 'データをエクスポートしました。');
            } else {
                showStatus('error', 'データのエクスポートに失敗しました。');
            }
        } catch (error) {
            showStatus('error', 'データのエクスポート中にエラーが発生しました。');
            console.error('Export error:', error);
        }
    }

    // データのクリア
    async function clearDatabaseData() {
        if (!confirm('本当にデータベースの内容をクリアしますか？この操作は元に戻せません。')) {
            return;
        }

        try {
            const response = await fetch('/admin/clear', {
                method: 'POST'
            });

            const result = await response.json();

            if (response.ok) {
                showStatus('success', 'データベースをクリアしました。');
                refreshDatabaseStats();
            } else {
                showStatus('error', result.error || 'データのクリアに失敗しました。');
            }
        } catch (error) {
            showStatus('error', 'データのクリア中にエラーが発生しました。');
            console.error('Clear error:', error);
        }
    }

    // ステータス表示
    function showStatus(type, message) {
        uploadStatus.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'}`;
        uploadStatus.textContent = message;
        uploadStatus.style.display = 'block';

        // 3秒後に自動で非表示
        setTimeout(() => {
            uploadStatus.style.display = 'none';
        }, 3000);
    }

    // アップロードエリアのリセット
    function resetUploadArea() {
        selectedFile = null;
        uploadBtn.disabled = true;
        fileInput.value = '';
        
        uploadArea.innerHTML = `
            <i class="fas fa-cloud-upload-alt fa-3x text-primary mb-3"></i>
            <h5>ファイルをドラッグ&ドロップ</h5>
            <p class="text-muted">またはクリックしてファイルを選択</p>
        `;
    }

    // ファイルサイズのフォーマット
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // データモーダルの表示
    function showDataModal(data) {
        // モーダルのHTMLを作成
        const modalHTML = `
            <div class="modal fade" id="dataModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">データベース内容</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6>原価マスター (${data.cost_master?.length || 0}件)</h6>
                                    <div class="table-responsive" style="max-height: 400px;">
                                        <table class="table table-sm">
                                            <thead class="table-light">
                                                <tr>
                                                    <th>材料名</th>
                                                    <th>容量</th>
                                                    <th>単位</th>
                                                    <th>単価</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${data.cost_master?.map(item => `
                                                    <tr>
                                                        <td>${item.ingredient_name || '-'}</td>
                                                        <td>${item.capacity || '-'}</td>
                                                        <td>${item.unit || '-'}</td>
                                                        <td>¥${item.unit_price || 0}</td>
                                                    </tr>
                                                `).join('') || '<tr><td colspan="4" class="text-center">データなし</td></tr>'}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <h6>レシピ (${data.recipes?.length || 0}件)</h6>
                                    <div class="table-responsive" style="max-height: 400px;">
                                        <table class="table table-sm">
                                            <thead class="table-light">
                                                <tr>
                                                    <th>料理名</th>
                                                    <th>人数</th>
                                                    <th>作成日</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${data.recipes?.map(item => `
                                                    <tr>
                                                        <td>${item.dish_name || '-'}</td>
                                                        <td>${item.servings || 0}人前</td>
                                                        <td>${new Date(item.created_at).toLocaleDateString()}</td>
                                                    </tr>
                                                `).join('') || '<tr><td colspan="3" class="text-center">データなし</td></tr>'}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">閉じる</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 既存のモーダルを削除
        const existingModal = document.getElementById('dataModal');
        if (existingModal) {
            existingModal.remove();
        }

        // 新しいモーダルを追加
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // モーダルを表示
        const modal = new bootstrap.Modal(document.getElementById('dataModal'));
        modal.show();
    }
});
