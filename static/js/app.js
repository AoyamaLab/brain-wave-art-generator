document.addEventListener('DOMContentLoaded', function () {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadSection = document.getElementById('uploadSection');
    const loadingSection = document.getElementById('loading');
    const resultSection = document.getElementById('resultSection');
    const errorDiv = document.getElementById('error');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const newAnalysisBtn = document.getElementById('newAnalysisBtn');
    const fileClearBtn = document.getElementById('fileClearBtn');

    // 結果タブ関連の要素
    const resultTabBtns = document.querySelectorAll('.result-tab-btn');
    const resultTabContents = document.querySelectorAll('.result-tab-content');

    let selectedFiles = [];

    // 結果タブ切り替え機能
    resultTabBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const targetTab = this.getAttribute('data-tab');

            // タブボタンのアクティブ状態を更新
            resultTabBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // タブコンテンツの表示を更新
            resultTabContents.forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(targetTab + '-tab').classList.add('active');
        });
    });

    // ファイルクリアボタン
    fileClearBtn.addEventListener('click', function () {
        selectedFiles = [];
        fileInput.value = '';
        fileInfo.style.display = 'none';
        uploadBtn.style.opacity = '0.6';
        uploadBtn.style.cursor = 'not-allowed';
        uploadBtn.textContent = '🎨 アート生成開始';
        uploadBtn.style.background = 'linear-gradient(45deg, #1e88e5, #42a5f5)';
        hideError();
    });

    // ファイルドラッグ＆ドロップ処理
    uploadArea.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        const files = Array.from(e.dataTransfer.files);
        handleFileSelection(files);
    });

    // ファイル選択ボタンクリック
    uploadArea.addEventListener('click', function () {
        fileInput.click();
    });

    // ファイル選択変更（複数ファイル対応）
    fileInput.addEventListener('change', function (e) {
        const files = Array.from(e.target.files);
        handleFileSelection(files);
    });

    // アップロードボタンクリック
    uploadBtn.addEventListener('click', function () {
        if (selectedFiles.length > 0) {
            uploadFiles(selectedFiles);
        } else {
            showError('ファイルを選択してください。');
        }
    });

    // 新しい解析ボタンクリック
    newAnalysisBtn.addEventListener('click', function () {
        resetForm();
    });

    function handleFileSelection(files) {
        // EEGファイルをフィルタリング
        const eegFiles = files.filter(file =>
            file.name.endsWith('.eeg') || file.name.endsWith('.vhdr')
        );

        if (eegFiles.length === 0) {
            showError('EEGファイル（.eeg または .vhdr）を選択してください。');
            return;
        }

        // 現在選択されているファイルと新しいファイルをマージ
        const newFiles = [...selectedFiles, ...eegFiles];

        // 重複を除去（ファイル名ベース）
        const uniqueFiles = newFiles.filter((file, index, self) =>
            index === self.findIndex(f => f.name === file.name)
        );

        // .eegと.vhdrのペアを探す
        const eegFile = uniqueFiles.find(file => file.name.endsWith('.eeg'));
        const vhdrFile = uniqueFiles.find(file => file.name.endsWith('.vhdr'));

        selectedFiles = uniqueFiles;

        // ファイル表示の更新
        if (eegFile && vhdrFile) {
            // 完璧なペアが見つかった場合
            fileName.textContent = `${eegFile.name} + ${vhdrFile.name}`;
            fileSize.textContent = formatFileSize(eegFile.size + vhdrFile.size);
            fileInfo.style.backgroundColor = 'rgba(76, 175, 80, 0.1)'; // 緑色のハイライト
        } else if (eegFile || vhdrFile) {
            // 単一ファイルの場合
            const singleFile = eegFile || vhdrFile;
            const fileType = eegFile ? 'データファイル' : 'ヘッダーファイル';
            const missingType = eegFile ? 'ヘッダーファイル(.vhdr)' : 'データファイル(.eeg)';

            fileName.textContent = `${singleFile.name} (${fileType})`;
            fileSize.textContent = `${formatFileSize(singleFile.size)} - ${missingType}が必要`;
            fileInfo.style.backgroundColor = 'rgba(255, 193, 7, 0.1)'; // 黄色のハイライト
        } else {
            showError('対応するファイル形式が見つかりません。');
            return;
        }

        fileInfo.style.display = 'block';

        // アップロードボタンの状態を更新
        if (eegFile && vhdrFile) {
            // 両方のファイルがある場合は完全に有効化
            uploadBtn.style.opacity = '1';
            uploadBtn.style.cursor = 'pointer';
            uploadBtn.style.background = 'linear-gradient(45deg, #1e88e5, #42a5f5)';
            uploadBtn.textContent = '🎨 アート生成開始';
        } else {
            // 片方しかない場合は部分的に有効化
            uploadBtn.style.opacity = '0.8';
            uploadBtn.style.cursor = 'pointer';
            uploadBtn.style.background = 'linear-gradient(45deg, #ff9800, #ffc107)';
            uploadBtn.textContent = '⚠️ もう一つのファイルを追加';
        }

        hideError();
    }

    function uploadFiles(files) {
        const formData = new FormData();

        // 複数ファイルを追加
        files.forEach(file => {
            formData.append('files', file);
        });

        // UI状態変更
        uploadSection.style.display = 'none';
        loadingSection.style.display = 'block';
        resultSection.style.display = 'none';
        hideError();

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                loadingSection.style.display = 'none';

                if (data.success) {
                    showResult(data);
                } else {
                    showError(data.error || '解析中にエラーが発生しました。');
                    resetForm();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                loadingSection.style.display = 'none';
                showError('ネットワークエラーが発生しました。もう一度お試しください。');
                resetForm();
            });
    }

    function showResult(data) {
        const resultImage = document.getElementById('resultImage');
        const downloadLink = document.getElementById('downloadLink');

        resultImage.src = data.image_data;
        downloadLink.href = data.image_data;
        downloadLink.download = data.filename || 'eeg_analysis.png';

        // 詳細解析情報を詳細解析タブに表示
        if (data.band_powers && data.signal_quality) {
            const analysisDetails = document.getElementById('analysisDetails');
            analysisDetails.innerHTML = `
                <div style="padding: 25px; background: rgba(0, 40, 80, 0.4); border-radius: 20px; border: 1px solid rgba(100, 200, 255, 0.3); backdrop-filter: blur(10px);">

                    <div style="margin: 25px 0;">
                        <h4 style="color: #4ECDC4; margin-bottom: 15px; font-size: 1.3em;">🔧 信号処理プロセス</h4>
                        <div style="background: rgba(0, 0, 0, 0.3); padding: 20px; border-radius: 15px; margin-bottom: 20px;">
                            <div style="color: #e1f5fe; line-height: 1.8; font-size: 1em;">
                                <div style="margin: 10px 0;"><span style="color: #64b5f6;">1. DC成分除去:</span> 直流成分を除去して信号をクリーンアップ</div>
                                <div style="margin: 10px 0;"><span style="color: #4ECDC4;">2. 電源ノイズ除去:</span> 50Hz/60Hzの電源由来ノイズを除去</div>
                                <div style="margin: 10px 0;"><span style="color: #96CEB4;">3. バンドパスフィルタ:</span> 0.1-100Hzの脳波帯域のみを抽出</div>
                                <div style="margin: 10px 0;"><span style="color: #FFEAA7;">4. アーティファクト除去:</span> 眼球運動や筋電図ノイズを除去</div>
                                <div style="margin: 10px 0;"><span style="color: #ff9800;">5. 信号平滑化:</span> 高周波ノイズを適応的フィルタで除去</div>
                                <div style="margin: 10px 0;"><span style="color: #ab47bc;">6. 正規化:</span> 信号を統一的なスケールに調整</div>
                            </div>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                            <div style="text-align: center; padding: 15px; background: rgba(100, 200, 255, 0.15); border-radius: 15px; border: 1px solid rgba(100, 200, 255, 0.2);">
                                <div style="font-size: 2rem; color: #64b5f6; font-weight: bold; margin-bottom: 5px;">${data.signal_quality.snr_improvement_db}</div>
                                <div style="font-size: 0.9rem; color: #b3e5fc;">SNR改善 (dB)</div>
                                <div style="font-size: 0.8rem; color: #81c784; margin-top: 5px;">信号品質向上</div>
                            </div>
                            <div style="text-align: center; padding: 15px; background: rgba(76, 175, 80, 0.15); border-radius: 15px; border: 1px solid rgba(76, 175, 80, 0.2);">
                                <div style="font-size: 2rem; color: #4ECDC4; font-weight: bold; margin-bottom: 5px;">${data.signal_quality.artifacts_removed}</div>
                                <div style="font-size: 0.9rem; color: #b3e5fc;">除去されたノイズ</div>
                                <div style="font-size: 0.8rem; color: #81c784; margin-top: 5px;">アーティファクト数</div>
                            </div>
                            <div style="text-align: center; padding: 15px; background: rgba(156, 39, 176, 0.15); border-radius: 15px; border: 1px solid rgba(156, 39, 176, 0.2);">
                                <div style="font-size: 2rem; color: #ab47bc; font-weight: bold; margin-bottom: 5px;">${data.signal_quality.noise_reduction_ratio.toFixed(1)}x</div>
                                <div style="font-size: 0.9rem; color: #b3e5fc;">ノイズ低減倍率</div>
                                <div style="font-size: 0.8rem; color: #81c784; margin-top: 5px;">クリーンアップ効果</div>
                            </div>
                        </div>
                    </div>

                    <div style="margin: 25px 0;">
                        <h4 style="color: #FFEAA7; margin-bottom: 15px; font-size: 1.3em;">📊 周波数帯域分布</h4>
                        <div style="background: rgba(0, 0, 0, 0.3); padding: 15px; border-radius: 10px; margin-bottom: 15px;">
                            ${Object.keys(data.band_powers).map(band => {
                const power = data.band_powers[band].power;
                const totalPower = Object.values(data.band_powers).reduce((sum, b) => sum + b.power, 0);
                const percentage = totalPower > 0 ? (power / totalPower * 100).toFixed(1) : '0.0';
                const barWidth = totalPower > 0 ? (power / Math.max(...Object.values(data.band_powers).map(b => b.power)) * 100) : 0;
                return `
                                    <div style="margin: 8px 0; display: flex; align-items: center;">
                                        <span style="color: ${data.band_powers[band].color}; font-size: 1.2em; margin-right: 10px;">●</span>
                                        <span style="color: #e1f5fe; font-weight: bold; width: 60px;">${band}:</span>
                                        <div style="flex-grow: 1; margin: 0 10px; background: rgba(255,255,255,0.1); border-radius: 5px; height: 8px; position: relative;">
                                            <div style="background: ${data.band_powers[band].color}; height: 100%; width: ${barWidth}%; border-radius: 5px; transition: width 1s ease;"></div>
                                        </div>
                                        <span style="color: #b3e5fc; font-weight: bold; width: 50px; text-align: right;">${percentage}%</span>
                                    </div>
                                `;
            }).join('')}
                        </div>
                        <div style="text-align: center; color: #b3e5fc; font-size: 0.9em; opacity: 0.8;">
                            各脳波帯域の分布を可視化。この分布データから美しいアート作品が生成されました。
                        </div>
                    </div>

                    <div style="margin-top: 25px; padding: 20px; background: rgba(100, 181, 246, 0.1); border-radius: 15px; border-left: 4px solid #64b5f6;">
                        <p style="color: #e1f5fe; font-size: 1em; line-height: 1.6; margin: 0;">
                            <i class="fas fa-info-circle" style="color: #64b5f6; margin-right: 8px;"></i>
                            <strong>処理について:</strong> 生の脳波信号に高度なデジタル信号処理を適用し、ノイズを除去した純粋な脳活動データを抽出。
                            このクリーンなデータから周波数解析を行い、各脳波帯域の強度に基づいてアルゴリズムが美しいアート作品を自動生成しています。
                        </p>
                    </div>
                </div>
            `;
        }

        resultSection.style.display = 'block';

        // 画像ロード完了後にアニメーション
        resultImage.onload = function () {
            resultImage.style.opacity = '0';
            resultImage.style.transform = 'scale(0.8)';

            setTimeout(() => {
                resultImage.style.transition = 'all 0.5s ease';
                resultImage.style.opacity = '1';
                resultImage.style.transform = 'scale(1)';
            }, 100);
        };
    }

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';

        // エラーメッセージを自動で隠す
        setTimeout(() => {
            hideError();
        }, 5000);
    }

    function hideError() {
        errorDiv.style.display = 'none';
    }

    function resetForm() {
        selectedFiles = [];
        fileInput.value = '';
        fileInfo.style.display = 'none';
        uploadSection.style.display = 'block';
        loadingSection.style.display = 'none';
        resultSection.style.display = 'none';
        hideError();

        // 詳細解析データをクリア
        const analysisDetails = document.getElementById('analysisDetails');
        if (analysisDetails) {
            analysisDetails.innerHTML = '';
        }

        // 結果タブを「アート」に戻す
        resultTabBtns.forEach(b => b.classList.remove('active'));
        resultTabContents.forEach(content => content.classList.remove('active'));
        document.querySelector('[data-tab="art-result"]').classList.add('active');
        document.getElementById('art-result-tab').classList.add('active');

        // アップロードボタンを無効化
        uploadBtn.style.opacity = '0.6';
        uploadBtn.style.cursor = 'not-allowed';
        uploadBtn.textContent = '🎨 アート生成開始';
        uploadBtn.style.background = 'linear-gradient(45deg, #1e88e5, #42a5f5)';
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // 初期状態でアップロードボタンを無効化
    uploadBtn.style.opacity = '0.6';
    uploadBtn.style.cursor = 'not-allowed';

    // ページロード時のアニメーション
    setTimeout(() => {
        document.querySelector('.title').style.opacity = '1';
        document.querySelector('.subtitle').style.opacity = '1';
        document.querySelector('.description').style.opacity = '1';
    }, 100);

    // パーティクルエフェクト（オプション）
    function createParticle() {
        const particle = document.createElement('div');
        particle.style.position = 'fixed';
        particle.style.width = '4px';
        particle.style.height = '4px';
        particle.style.background = 'rgba(100, 181, 246, 0.6)';
        particle.style.borderRadius = '50%';
        particle.style.pointerEvents = 'none';
        particle.style.zIndex = '1';
        particle.style.left = Math.random() * window.innerWidth + 'px';
        particle.style.top = window.innerHeight + 'px';
        particle.style.boxShadow = '0 0 10px rgba(100, 181, 246, 0.8)';

        document.body.appendChild(particle);

        const animation = particle.animate([
            {
                transform: 'translateY(0px) translateX(0px)',
                opacity: 0
            },
            {
                transform: `translateY(-${window.innerHeight + 100}px) translateX(${(Math.random() - 0.5) * 100}px)`,
                opacity: 1
            },
            {
                transform: `translateY(-${window.innerHeight + 200}px) translateX(${(Math.random() - 0.5) * 200}px)`,
                opacity: 0
            }
        ], {
            duration: 8000 + Math.random() * 4000,
            easing: 'ease-out'
        });

        animation.onfinish = () => {
            particle.remove();
        };
    }

    // パーティクルを定期的に生成
    setInterval(createParticle, 2000);
});