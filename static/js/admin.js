// データベース管理システム JavaScript
console.log('🚀 Admin.js loaded successfully');

document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 DOM Content Loaded');
    
    // 要素の取得
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadStatus = document.getElementById('uploadStatus');
    const downloadBtn = document.getElementById('downloadBtn');
    const downloadTransactionBtn = document.getElementById('downloadTransactionBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    const viewDataBtn = document.getElementById('viewDataBtn');
    const exportDataBtn = document.getElementById('exportDataBtn');
    const clearDataBtn = document.getElementById('clearDataBtn');
    
    // 要素の存在確認
    console.log('✅ Elements check:', {
        uploadArea: !!uploadArea,
        fileInput: !!fileInput,
        uploadBtn: !!uploadBtn,
        downloadBtn: !!downloadBtn,
        downloadTransactionBtn: !!downloadTransactionBtn,
        refreshBtn: !!refreshBtn,
        viewDataBtn: !!viewDataBtn,
        exportDataBtn: !!exportDataBtn,
        clearDataBtn: !!clearDataBtn
    });
    
    // 重要な要素のみチェック
    const criticalElements = [];
    if (!uploadArea) criticalElements.push('uploadArea');
    if (!fileInput) criticalElements.push('fileInput');
    if (!uploadBtn) criticalElements.push('uploadBtn');
    
    if (criticalElements.length > 0) {
        console.error('❌ Critical elements missing:', criticalElements);
        console.log('⚠️ 重要な要素が見つからないため、一部機能が制限されます');
    } else {
        console.log('✅ All critical elements found');
    }
    
    // オプション要素の確認
    const optionalElements = [];
    if (!downloadBtn) optionalElements.push('downloadBtn');
    if (!downloadTransactionBtn) optionalElements.push('downloadTransactionBtn');
    if (!refreshBtn) optionalElements.push('refreshBtn');
    if (!viewDataBtn) optionalElements.push('viewDataBtn');
    if (!exportDataBtn) optionalElements.push('exportDataBtn');
    if (!clearDataBtn) optionalElements.push('clearDataBtn');
    
    if (optionalElements.length > 0) {
        console.warn('⚠️ Optional elements missing:', optionalElements);
    }
    
    let selectedFile = null;

    // ファイルアップロード関連のイベント（要素が存在する場合のみ）
    if (uploadArea && fileInput) {
        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', handleDragOver);
        uploadArea.addEventListener('dragleave', handleDragLeave);
        uploadArea.addEventListener('drop', handleDrop);
        fileInput.addEventListener('change', handleFileSelect);
    }

    // ボタンイベント（要素が存在する場合のみ）
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            console.log('🔼 Upload button clicked');
            uploadFile();
        });
    }
    
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            console.log('📥 Download button clicked');
            downloadTemplate();
        });
    }
    
    if (downloadTransactionBtn) {
        downloadTransactionBtn.addEventListener('click', () => {
            console.log('📥 Transaction template button clicked');
            downloadTransactionTemplate();
        });
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            console.log('🔄 Refresh button clicked');
            refreshDatabaseStats();
        });
    }
    
    if (viewDataBtn) {
        viewDataBtn.addEventListener('click', () => {
            console.log('👁️ View data button clicked');
            viewDatabaseData();
        });
    }
    
    if (exportDataBtn) {
        exportDataBtn.addEventListener('click', () => {
            console.log('💾 Export button clicked');
            exportDatabaseData();
        });
    }
    
    if (clearDataBtn) {
        clearDataBtn.addEventListener('click', () => {
            console.log('🗑️ Clear button clicked');
            clearDatabaseData();
        });
    }

    console.log('✅ All event listeners attached');

    // 初期化
    console.log('🔄 Initializing stats...');
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
        console.log('📤 uploadFile() called');
        
        if (!selectedFile) {
            console.error('❌ No file selected');
            showStatus('error', 'ファイルが選択されていません。');
            return;
        }

        // アップロードタイプを取得（デフォルトはcost_master）
        let uploadType = 'cost_master';
        let endpoint = '/admin/upload';
        
        const uploadTypeElement = document.querySelector('input[name="uploadType"]:checked');
        if (uploadTypeElement) {
            uploadType = uploadTypeElement.value;
            endpoint = uploadType === 'transaction' ? '/admin/upload-transaction' : '/admin/upload';
            console.log('📋 Upload type found:', uploadType);
        } else {
            console.warn('⚠️ Upload type radio button not found, using default: cost_master');
            // デフォルトでcost_masterを使用
        }
        
        console.log('📋 Upload details:', {
            file: selectedFile.name,
            size: selectedFile.size,
            type: uploadType,
            endpoint: endpoint
        });

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            uploadBtn.disabled = true;
            uploadProgress.style.display = 'block';
            
            if (uploadType === 'transaction') {
                showStatus('info', '取引データを解析・抽出中...');
            } else {
                showStatus('info', 'ファイルをアップロード中...');
            }

            console.log('🌐 Sending fetch request to:', endpoint);
            
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });
            
            console.log('📨 Response received:', {
                status: response.status,
                ok: response.ok,
                statusText: response.statusText
            });

            const result = await response.json();
            console.log('📊 Response data:', result);

            if (response.ok) {
                if (uploadType === 'transaction') {
                    showStatus('success', `取引データ処理完了！\n処理: ${result.processed}件\n抽出: ${result.extracted}件\n保存: ${result.saved}件`);
                } else {
                    showStatus('success', `アップロード完了！${result.count}件のデータが登録されました。`);
                }
                resetUploadArea();
                refreshDatabaseStats();
            } else {
                console.error('❌ Upload failed:', result);
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
        try {
            const templateType = document.querySelector('input[name=\"templateType\"]:checked').value;
            const downloadUrl = `/admin/template?type=${templateType}`;
            window.location.href = downloadUrl;
            
            // ユーザーへのフィードバック（ダウンロードが開始されたことを示す）
            showStatus('info', 'テンプレートのダウンロードを開始します...');

        } catch (error) {
            showStatus('error', 'テンプレートのダウンロードに失敗しました。');
            console.error('Download error:', error);
        }
    }

    // 取引データテンプレートダウンロード
    function downloadTransactionTemplate() {
        fetch('/admin/template-transaction')
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'transaction_template.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showStatus('success', '取引データテンプレートをダウンロードしました。');
            })
            .catch(error => {
                showStatus('error', '取引データテンプレートのダウンロードに失敗しました。');
                console.error('Transaction template download error:', error);
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
        // モーダルを作成して選択肢を表示
        const modalHTML = `
            <div class="modal fade" id="clearModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content" style="background-color: #2a2a3e; color: #e0e0e0; border: 1px solid rgba(255, 255, 255, 0.1);">
                        <div class="modal-header" style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                            <h5 class="modal-title" style="color: #e57373;">
                                <i class="fas fa-exclamation-triangle me-2"></i>データクリア
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-3">削除するデータを選択してください：</p>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" id="clearCostMaster" checked>
                                <label class="form-check-label" for="clearCostMaster">
                                    登録材料（原価マスター）
                                </label>
                            </div>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" id="clearRecipes">
                                <label class="form-check-label" for="clearRecipes">
                                    保存レシピ
                                </label>
                            </div>
                            <div class="alert alert-warning mt-3" style="background-color: rgba(255, 193, 7, 0.1); border-color: #ffc107; color: #ffc107;">
                                <i class="fas fa-exclamation-circle me-2"></i>
                                この操作は元に戻せません！
                            </div>
                            <div class="mt-3">
                                <label for="confirmText" class="form-label">確認のため「クリア」と入力してください：</label>
                                <input type="text" class="form-control" id="confirmText" style="background-color: #1a1a2e; color: #e0e0e0; border-color: rgba(255, 255, 255, 0.2);">
                            </div>
                        </div>
                        <div class="modal-footer" style="border-top: 1px solid rgba(255, 255, 255, 0.1);">
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">キャンセル</button>
                            <button type="button" class="btn btn-danger" id="confirmClearBtn">
                                <i class="fas fa-trash-alt me-2"></i>クリア実行
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 既存のモーダルを削除
        const existingModal = document.getElementById('clearModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // 新しいモーダルを追加
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // モーダルを表示
        const clearModal = new bootstrap.Modal(document.getElementById('clearModal'));
        clearModal.show();
        
        // クリア実行ボタンのイベント
        document.getElementById('confirmClearBtn').addEventListener('click', async function() {
            const confirmText = document.getElementById('confirmText').value;
            const clearCostMaster = document.getElementById('clearCostMaster').checked;
            const clearRecipes = document.getElementById('clearRecipes').checked;
            
            if (confirmText !== 'クリア') {
                showStatus('error', '確認テキストが正しくありません。');
                return;
            }
            
            if (!clearCostMaster && !clearRecipes) {
                showStatus('error', '削除するデータを選択してください。');
                return;
            }
            
            try {
                clearModal.hide();
                
                const response = await fetch('/admin/clear', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        clear_cost_master: clearCostMaster,
                        clear_recipes: clearRecipes
                    })
                });

                const result = await response.json();

                if (response.ok) {
                    let message = 'データをクリアしました：';
                    if (clearCostMaster) message += '\n・登録材料';
                    if (clearRecipes) message += '\n・保存レシピ';
                    showStatus('success', message);
                    refreshDatabaseStats();
                } else {
                    showStatus('error', result.error || 'データのクリアに失敗しました。');
                }
            } catch (error) {
                showStatus('error', 'データのクリア中にエラーが発生しました。');
                console.error('Clear error:', error);
            }
        });
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
                    <div class="modal-content" style="background-color: #2a2a3e; color: #e0e0e0; border: 1px solid rgba(255, 255, 255, 0.1);">
                        <div class="modal-header" style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                            <h5 class="modal-title" style="color: #64b5f6;">データベース内容</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6 style="color: #81c784;">原価マスター (${data.cost_master?.length || 0}件)</h6>
                                    <div class="table-responsive" style="max-height: 400px;">
                                        <table class="table table-sm table-dark">
                                            <thead style="background-color: rgba(100, 181, 246, 0.2);">
                                                <tr>
                                                    <th>材料名</th>
                                                    <th>取引先</th>
                                                    <th>容量</th>
                                                    <th>単位</th>
                                                    <th>単価</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${data.cost_master?.map(item => {
                                                    // 容量の表示（小数点以下を削除）
                                                    const capacity = item.capacity || 0;
                                                    const capacityDisplay = capacity === parseInt(capacity) ? 
                                                        parseInt(capacity).toString() : 
                                                        capacity.toString();
                                                    
                                                    // 単位情報の表示（unit_columnを優先）
                                                    // unit_columnがnullでない場合は、空文字列でもそれを尊重する
                                                    let unitDisplay;
                                                    if (item.unit_column !== null && item.unit_column !== undefined) {
                                                        // unit_columnが存在する場合は、それを表示（空文字列の場合は容量のみ）
                                                        unitDisplay = item.unit_column || capacityDisplay;
                                                    } else {
                                                        // unit_columnが存在しない場合は、unitを表示
                                                        unitDisplay = item.unit || '-';
                                                    }
                                                    
                                                    // 単価の表示（小数点以下を削除）
                                                    const unitPrice = item.unit_price || 0;
                                                    const unitPriceDisplay = unitPrice === parseInt(unitPrice) ? 
                                                        parseInt(unitPrice) : 
                                                        unitPrice;
                                                    
                                                    return `
                                                    <tr>
                                                        <td>${item.ingredient_name || '-'}</td>
                                                        <td>${item.suppliers?.name || '-'}</td>
                                                        <td>${capacityDisplay}</td>
                                                        <td>${unitDisplay}</td>
                                                        <td>¥${unitPriceDisplay}</td>
                                                    </tr>
                                                    `;
                                                }).join('') || '<tr><td colspan="5" class="text-center">データなし</td></tr>'}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <h6 style="color: #81c784;">レシピ (${data.recipes?.length || 0}件)</h6>
                                    <div class="table-responsive" style="max-height: 400px;">
                                        <table class="table table-sm table-dark">
                                            <thead style="background-color: rgba(100, 181, 246, 0.2);">
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
                        <div class="modal-footer" style="border-top: 1px solid rgba(255, 255, 255, 0.1);">
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">閉じる</button>
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
