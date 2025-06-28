from flask import Flask, render_template, request, jsonify
import numpy as np
from scipy.fft import fft, fftfreq
import matplotlib
matplotlib.use('Agg')  # バックエンドを設定
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Circle
import os
import tempfile
import struct
from werkzeug.utils import secure_filename
import io
import base64
from scipy import signal
from scipy.signal import butter, filtfilt, iirnotch

app = Flask(__name__)

# セキュリティ設定
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['DejaVu Sans', 'Liberation Sans', 'Arial', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

class AdvancedEEGProcessor:
    def __init__(self):
        self.sampling_rate = 512  # Hz
        self.frequency_bands = {
            'Delta': {'range': '0.5-4 Hz', 'color': '#FF6B6B', 'freq': (0.5, 4)},
            'Theta': {'range': '4-8 Hz', 'color': '#4ECDC4', 'freq': (4, 8)},
            'Alpha': {'range': '8-13 Hz', 'color': '#45B7D1', 'freq': (8, 13)},
            'Beta': {'range': '13-30 Hz', 'color': '#96CEB4', 'freq': (13, 30)},
            'Gamma': {'range': '30-100 Hz', 'color': '#FFEAA7', 'freq': (30, 100)}
        }

    def parse_header(self, vhdr_path):
        """VHDRファイルを解析してメタデータを取得"""
        metadata = {}
        with open(vhdr_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # サンプリング周波数を取得
        for line in content.split('\n'):
            if 'SamplingInterval=' in line:
                interval = float(line.split('=')[1])
                self.sampling_rate = int(1000000 / interval)  # マイクロ秒から Hz に変換
                break

        return metadata

    def load_eeg_data(self, eeg_path, vhdr_path):
        """EEGデータを読み込み"""
        try:
            # ヘッダー情報を取得
            self.parse_header(vhdr_path)

            # バイナリデータを読み込み
            with open(eeg_path, 'rb') as f:
                data = f.read()

            # 16-bit signed integerとして解析
            num_samples = len(data) // 2
            eeg_data = struct.unpack('<' + str(num_samples) + 'h', data)

            return np.array(eeg_data, dtype=np.float32)

        except Exception as e:
            print(f"Error loading EEG data: {e}")
            return None

    def remove_dc_component(self, data):
        """DC成分（直流成分）の除去"""
        return data - np.mean(data)

    def bandpass_filter(self, data, low_freq, high_freq, order=4):
        """バンドパスフィルタ（指定周波数帯域のみ通す）"""
        nyquist = self.sampling_rate / 2
        low = low_freq / nyquist
        high = high_freq / nyquist

        # Butterworthフィルタを使用
        b, a = butter(order, [low, high], btype='band')
        filtered_data = filtfilt(b, a, data)

        return filtered_data

    def notch_filter(self, data, freq_to_remove=50.0, quality_factor=30):
        """ノッチフィルタ（特定周波数を除去、電源ノイズ除去）"""
        nyquist = self.sampling_rate / 2
        freq_norm = freq_to_remove / nyquist

        # IIRノッチフィルタ
        b, a = iirnotch(freq_norm, quality_factor)
        filtered_data = filtfilt(b, a, data)

        return filtered_data

    def remove_artifacts_zscore(self, data, threshold=3.0):
        """Z-scoreを使ったアーティファクト除去"""
        # Z-scoreを計算
        z_scores = np.abs((data - np.mean(data)) / np.std(data))

        # 閾値を超える値を中央値で置き換え
        median_value = np.median(data)
        cleaned_data = data.copy()
        cleaned_data[z_scores > threshold] = median_value

        return cleaned_data

    def moving_average_filter(self, data, window_size=5):
        """移動平均フィルタ（高周波ノイズの平滑化）"""
        if window_size < 1:
            return data

        # 畳み込みを使った移動平均
        kernel = np.ones(window_size) / window_size
        filtered_data = np.convolve(data, kernel, mode='same')

        return filtered_data

    def adaptive_filter(self, data, window_length=None):
        """適応的フィルタ（Savitzky-Golayフィルタ）"""
        if window_length is None:
            window_length = max(5, int(self.sampling_rate * 0.01))  # 10ms window

        # 奇数にする
        if window_length % 2 == 0:
            window_length += 1

        try:
            from scipy.signal import savgol_filter
            filtered_data = savgol_filter(data, window_length, 3)
            return filtered_data
        except:
            # Savitzky-Golayが使えない場合は移動平均にフォールバック
            return self.moving_average_filter(data, window_length//2)

    def comprehensive_noise_removal(self, data):
        """包括的なノイズ除去処理"""
        print("🔧 Starting comprehensive noise removal...")

        # 1. DC成分除去
        print("  📊 Removing DC component...")
        cleaned_data = self.remove_dc_component(data)

        # 2. 電源ノイズ除去（50Hz, 60Hz）
        print("  ⚡ Removing power line noise (50Hz, 60Hz)...")
        cleaned_data = self.notch_filter(cleaned_data, 50.0)  # 50Hz除去
        cleaned_data = self.notch_filter(cleaned_data, 60.0)  # 60Hz除去

        # 3. バンドパスフィルタ（0.1-100Hz: 一般的なEEG帯域）
        print("  🎛️ Applying bandpass filter (0.1-100Hz)...")
        cleaned_data = self.bandpass_filter(cleaned_data, 0.1, 100.0)

        # 4. アーティファクト除去
        print("  🧹 Removing artifacts using Z-score method...")
        cleaned_data = self.remove_artifacts_zscore(cleaned_data, threshold=3.5)

        # 5. 高周波ノイズの平滑化
        print("  🌊 Smoothing high-frequency noise...")
        cleaned_data = self.adaptive_filter(cleaned_data)

        # 6. 最終的な正規化
        print("  📏 Final normalization...")
        cleaned_data = cleaned_data / np.std(cleaned_data)

        print("✅ Noise removal completed!")
        return cleaned_data

    def analyze_signal_quality(self, original_data, cleaned_data):
        """信号品質の分析"""
        # SNR計算（簡易版）
        signal_power = np.var(cleaned_data)
        noise_power = np.var(original_data - cleaned_data)
        snr = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else float('inf')

        # アーティファクトの検出数
        z_scores_orig = np.abs((original_data - np.mean(original_data)) / np.std(original_data))
        artifacts_removed = np.sum(z_scores_orig > 3.5)

        return {
            'snr_improvement': snr,
            'artifacts_removed': artifacts_removed,
            'signal_variance_reduction': np.var(original_data) / np.var(cleaned_data)
        }

    def analyze_frequency_bands(self, data):
        """周波数帯域解析（ノイズ除去後）"""
        if data is None or len(data) == 0:
            return None

        # 2秒間のデータを使用
        duration = 2  # seconds
        n_samples = min(len(data), int(self.sampling_rate * duration))
        segment = data[:n_samples]

        # FFT実行
        fft_values = np.abs(fft(segment))
        freqs = fftfreq(len(segment), 1/self.sampling_rate)

        # 正の周波数のみを使用
        positive_freqs = freqs[:len(freqs)//2]
        positive_fft = fft_values[:len(fft_values)//2]

        # 各周波数帯域のパワーを計算
        band_powers = {}
        for band_name, band_info in self.frequency_bands.items():
            freq_min, freq_max = band_info['freq']
            mask = (positive_freqs >= freq_min) & (positive_freqs <= freq_max)
            band_power = np.sum(positive_fft[mask] ** 2) if np.any(mask) else 0

            band_powers[band_name] = {
                'power': float(band_power),
                'range': band_info['range'],
                'color': band_info['color']
            }

        return band_powers

def create_beautiful_visualization(band_powers, patient_name="Subject-01"):
    """アーティスティックで幻想的な脳波可視化画像を生成"""

    # 高解像度設定
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(20, 16), facecolor='#0a0a1a')

    # 単一の大きなキャンバス
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0a0a1a')
    ax.axis('off')

    # データ準備
    bands = list(band_powers.keys())
    powers = [band_powers[band]['power'] for band in bands]
    colors = [band_powers[band]['color'] for band in bands]

    # 正規化
    max_power = max(powers) if max(powers) > 0 else 1
    normalized_powers = [p/max_power for p in powers]

    # 背景グラデーション（深海のような）
    x = np.linspace(0, 1, 256)
    y = np.linspace(0, 1, 256)
    X, Y = np.meshgrid(x, y)

    # 深海から浅瀬へのグラデーション
    background = np.sqrt((X-0.5)**2 + (Y-0.7)**2)
    ax.imshow(background, extent=[0, 1, 0, 1], cmap='Blues_r', alpha=0.6, aspect='auto')

    # 中央に人影のシルエット（抽象的）
    center_x, center_y = 0.5, 0.45

    # 脳波の流れを表現する流線
    theta = np.linspace(0, 4*np.pi, 1000)

    for i, (band, power, color) in enumerate(zip(bands, normalized_powers, colors)):
        # 各周波数帯域を異なる流線パターンで表現
        angle_offset = i * 2 * np.pi / len(bands)

        # 流線の強さを脳波パワーで調整
        amplitude = 0.1 + power * 0.15
        frequency = 2 + i * 0.5

        # 美しい螺旋状の流線
        r = amplitude * (1 + 0.3 * np.sin(frequency * theta))
        x_flow = center_x + r * np.cos(theta + angle_offset)
        y_flow = center_y + r * np.sin(theta + angle_offset) * 0.7

        # 透明度と色を調整
        alpha_values = np.linspace(0.8, 0.1, len(theta))

        # 流線を描画（グラデーション効果）
        for j in range(0, len(theta)-1, 3):
            if 0 <= x_flow[j] <= 1 and 0 <= y_flow[j] <= 1:
                ax.plot([x_flow[j], x_flow[j+1]], [y_flow[j], y_flow[j+1]],
                       color=color, alpha=alpha_values[j], linewidth=2+power*3)

        # パーティクルエフェクト（泡のような）
        for _ in range(int(20 + power * 30)):
            bubble_x = center_x + np.random.normal(0, amplitude)
            bubble_y = center_y + np.random.normal(0, amplitude * 0.7)
            bubble_size = np.random.uniform(10, 50) * (0.5 + power)

            circle = Circle((bubble_x, bubble_y), bubble_size/1000,
                              color=color, alpha=np.random.uniform(0.2, 0.6))
            ax.add_patch(circle)

    # 中央の発光エフェクト
    gradient_x = np.linspace(center_x-0.2, center_x+0.2, 100)
    gradient_y = np.linspace(center_y-0.2, center_y+0.2, 100)
    GX, GY = np.meshgrid(gradient_x, gradient_y)

    # 放射状のグラデーション
    radial_dist = np.sqrt((GX-center_x)**2 + (GY-center_y)**2)
    glow = np.exp(-radial_dist*15)

    ax.imshow(glow, extent=[center_x-0.2, center_x+0.2, center_y-0.2, center_y+0.2],
             cmap='plasma', alpha=0.4, aspect='auto')

    # タイトルと情報を芸術的に配置（ASCII文字のみ使用）
    ax.text(0.5, 0.95, f'* {patient_name} *',
           fontsize=32, color='white', ha='center', va='top',
           fontweight='bold', alpha=0.9,
           bbox=dict(boxstyle='round,pad=0.5', facecolor='black', alpha=0.3))

    ax.text(0.5, 0.88, f'Brain Wave Symphony',
           fontsize=20, color='cyan', ha='center', va='top',
           style='italic', alpha=0.8)

    # 周波数帯域の情報を美しく配置
    info_text = ""
    for i, band in enumerate(bands):
        power = band_powers[band]['power']
        percentage = (power / sum(powers) * 100) if sum(powers) > 0 else 0
        info_text += f"{band}: {percentage:.1f}%  "

    ax.text(0.5, 0.12, info_text,
           fontsize=14, color='white', ha='center', va='bottom',
           alpha=0.7, style='italic')

    # 装飾的な境界線
    border_theta = np.linspace(0, 2*np.pi, 200)
    border_r = 0.48
    border_x = 0.5 + border_r * np.cos(border_theta)
    border_y = 0.5 + border_r * np.sin(border_theta)

    ax.plot(border_x, border_y, color='cyan', alpha=0.3, linewidth=1)

    # 座標軸の設定
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')

    # 高品質で保存
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', facecolor='#0a0a1a',
                dpi=300, bbox_inches='tight', edgecolor='none',
                transparent=False, pad_inches=0.1)
    img_buffer.seek(0)
    plt.close()

    return img_buffer

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_eeg():
    try:
        # 複数ファイルの取得
        files = request.files.getlist('files')

        if not files or len(files) == 0:
            return jsonify({'success': False, 'error': 'ファイルが選択されていません。'})

        # EEGファイルとVHDRファイルを分離
        eeg_file = None
        vhdr_file = None

        for file in files:
            if file and file.filename:
                if file.filename.endswith('.eeg'):
                    eeg_file = file
                elif file.filename.endswith('.vhdr'):
                    vhdr_file = file

        # どちらか一方しかない場合の処理
        if eeg_file and not vhdr_file:
            # .eegファイルのみの場合、対応する.vhdrファイルを探す
            return jsonify({'success': False, 'error': '対応するヘッダーファイル(.vhdr)が必要です。両方のファイルを選択してください。'})

        elif vhdr_file and not eeg_file:
            # .vhdrファイルのみの場合、対応する.eegファイルを探す
            return jsonify({'success': False, 'error': '対応するデータファイル(.eeg)が必要です。両方のファイルを選択してください。'})

        elif not eeg_file and not vhdr_file:
            return jsonify({'success': False, 'error': 'サポートされていないファイル形式です。.eegと.vhdrファイルを選択してください。'})

        # 両方のファイルがある場合の処理
        eeg_filename = secure_filename(eeg_file.filename)
        vhdr_filename = secure_filename(vhdr_file.filename)

        eeg_path = f"/tmp/{eeg_filename}"
        vhdr_path = f"/tmp/{vhdr_filename}"

        # ファイルを保存
        eeg_file.save(eeg_path)
        vhdr_file.save(vhdr_path)

        # EEG解析
        processor = AdvancedEEGProcessor()
        eeg_data = processor.load_eeg_data(eeg_path, vhdr_path)

        if eeg_data is None:
            return jsonify({'success': False, 'error': 'EEGデータの読み込みに失敗しました。ファイル形式を確認してください。'})

        # ノイズ除去
        cleaned_data = processor.comprehensive_noise_removal(eeg_data)

        if cleaned_data is None:
            return jsonify({'success': False, 'error': 'ノイズ除去に失敗しました。'})

        # 信号品質の分析
        quality_metrics = processor.analyze_signal_quality(eeg_data, cleaned_data)

        # 周波数解析
        band_powers = processor.analyze_frequency_bands(cleaned_data)

        if band_powers is None:
            return jsonify({'success': False, 'error': '周波数解析に失敗しました。'})

        # 可視化画像を生成
        patient_name = "Brain Wave Art"
        img_buffer = create_beautiful_visualization(band_powers, patient_name)

        # Base64エンコード
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        img_data_url = f"data:image/png;base64,{img_base64}"

        # 一時ファイルを削除
        try:
            os.remove(eeg_path)
            os.remove(vhdr_path)
        except:
            pass

        # 優勢な周波数帯域を特定
        dominant_band = max(band_powers.keys(), key=lambda x: band_powers[x]['power'])

        return jsonify({
            'success': True,
            'image_data': img_data_url,
            'filename': f'brain_wave_art_{eeg_filename.split(".")[0]}.png',
            'dominant_band': dominant_band,
            'band_powers': band_powers,
            'signal_quality': {
                'snr_improvement_db': round(quality_metrics['snr_improvement'], 2),
                'artifacts_removed': int(quality_metrics['artifacts_removed']),
                'noise_reduction_ratio': round(quality_metrics['signal_variance_reduction'], 2)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'エラーが発生しました: {str(e)}'})

@app.route('/analyze', methods=['POST'])
def analyze_eeg():
    try:
        # ファイルの取得
        files = request.files.getlist('files')
        patient_name = request.form.get('patient_name', 'Subject-01')

        eeg_file = None
        vhdr_file = None

        # .eegと.vhdrファイルを特定
        for file in files:
            if file and file.filename:
                if file.filename.endswith('.eeg'):
                    eeg_file = file
                elif file.filename.endswith('.vhdr'):
                    vhdr_file = file

        if not eeg_file or not vhdr_file:
            return jsonify({'success': False, 'error': 'EEGファイル(.eeg)とヘッダーファイル(.vhdr)の両方が必要です。'})

        # ファイルを一時的に保存
        eeg_filename = secure_filename(eeg_file.filename) if eeg_file.filename else 'temp.eeg'
        vhdr_filename = secure_filename(vhdr_file.filename) if vhdr_file.filename else 'temp.vhdr'

        eeg_path = f"/tmp/{eeg_filename}"
        vhdr_path = f"/tmp/{vhdr_filename}"

        eeg_file.save(eeg_path)
        vhdr_file.save(vhdr_path)

        # EEG解析
        processor = AdvancedEEGProcessor()
        eeg_data = processor.load_eeg_data(eeg_path, vhdr_path)

        if eeg_data is None:
            return jsonify({'success': False, 'error': 'EEGデータの読み込みに失敗しました。'})

        # ノイズ除去
        cleaned_data = processor.comprehensive_noise_removal(eeg_data)

        if cleaned_data is None:
            return jsonify({'success': False, 'error': 'ノイズ除去に失敗しました。'})

        # 信号品質の分析
        quality_metrics = processor.analyze_signal_quality(eeg_data, cleaned_data)

        # 周波数解析
        band_powers = processor.analyze_frequency_bands(cleaned_data)

        if band_powers is None:
            return jsonify({'success': False, 'error': '周波数解析に失敗しました。'})

        # 可視化画像を生成
        img_buffer = create_beautiful_visualization(band_powers, patient_name)

        # Base64エンコード
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        img_data_url = f"data:image/png;base64,{img_base64}"

        # 一時ファイルを削除
        try:
            os.remove(eeg_path)
            os.remove(vhdr_path)
        except:
            pass

        # 優勢な周波数帯域を特定
        dominant_band = max(band_powers.keys(), key=lambda x: band_powers[x]['power'])

        return jsonify({
            'success': True,
            'image': img_data_url,
            'dominant_band': dominant_band,
            'band_powers': band_powers,
            'signal_quality': {
                'snr_improvement_db': round(quality_metrics['snr_improvement'], 2),
                'artifacts_removed': int(quality_metrics['artifacts_removed']),
                'noise_reduction_ratio': round(quality_metrics['signal_variance_reduction'], 2)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'エラーが発生しました: {str(e)}'})

if __name__ == '__main__':
    print("🧠 EEG Beautiful Visualizer")
    print("Server starting...")

    # 環境変数から設定を取得（本番環境では環境変数で設定）
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'

    app.run(host=host, port=port, debug=debug)