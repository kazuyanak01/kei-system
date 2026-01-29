import streamlit as st
import pandas as pd
import re
import math

# --- 1. 定数定義（一切の省略なし） ---
COURSE_MAP = {
    '芝': {'中山1200':-2, '中山2500':-3, '中京1200':-2, '新潟1000':-5, '小倉1200':-3},
    'ダ': {'東京1300':1, '東京1600':-5, '東京2100':-2, '中山1200':-2, '中山1800':2, '中山2400':-3, '中山2500':-3, '中京1400':-3, '中京1900':-2, '京都1400':-2, '京都1900':-2, '阪神2000':-2, '新潟1200':-2, '新潟2500':-3, '小倉1000':-3, '小倉1700':1, '小倉2400':-3, '福島1700':1, '福島2400':-2, '札幌1000':1, '札幌2400':-2, '函館1000':1, '函館2400':-2}
}

def get_cat(surface, dist):
    try:
        d = int(dist)
        if surface == '芝':
            if d <= 1100: return 1
            elif d <= 1400: return 2
            elif d == 1600: return 3
            elif d <= 2500: return 4
            return 5
        else: # ダート
            if d <= 1000: return 1
            elif d <= 1200: return 2
            elif d <= 1400: return 3
            elif d <= 1600: return 4
            elif d <= 1800: return 5
            elif d <= 2100: return 6
            return 7
    except: return 0

def check_mismatch(old_s, old_d, cur_s, cur_d):
    o, n = get_cat(old_s, old_d), get_cat(cur_s, cur_d)
    if cur_s == '芝':
        if o in [1,2] and n in [3,4,5]: return True
        if o == 3 and n in [4,5]: return True
        if o == 5 and n != 5: return True
    else:
        if o == 1 and n != 1: return True
        if o in [2,3] and n in [4,5,6,7]: return True
        if o in [6,7] and n not in [6,7]: return True
    return False

def get_rank(s):
    if s >= 70: return 'S'
    elif s >= 65: return 'A+'
    elif s >= 60: return 'A'
    elif s >= 55: return 'B'
    elif s >= 50: return 'C'
    return 'D'

st.set_page_config(page_title="KEI System Pro", layout="wide")
st.title("🐎 KEI能力評価エンジン (最終運用モデル)")

input_text = st.text_area("netkeibaのデータを貼り付けてください", height=300)

if st.button("KEI指数を算出"):
    if not input_text:
        st.warning("データを入力してください")
    else:
        try:
            # A. レース条件の特定 (テキストの先頭1000文字以内から厳格抽出)
            header = input_text[:2000]
            b_raw = int(re.search(r'タイム指数\s*\n\s*(\d+)', header).group(1))
            venue = re.search(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', header).group(1)
            course_m = re.search(r'(芝|ダ)(\d+)m', header)
            cur_s, cur_d = course_m.groups()
            b_final = b_raw + (0 if "未勝利" in header else 5) + COURSE_MAP.get(cur_s, {}).get(f"{venue}{cur_d}", 0)
            
            st.info(f"【設定確認】今回の条件: {venue}{cur_s}{cur_d}m / B_final: {b_final}")

            # B. 馬ごとの分割 ( -- という記号を絶対基準にする)
            parts = re.split(r'(\d{1,2})\n\s*--\n', input_text)
            horses_list = []
            
            for i in range(1, len(parts), 2):
                h_num = int(parts[i])
                h_data = parts[i+1]
                
                # 馬名抽出：記号行を飛ばした最初の意味のある文字列
                lines = [l.strip() for l in h_data.split('\n') if l.strip()]
                h_name = "不明"
                for l in lines:
                    if any(m in l for m in ['◎','◯','▲','△','☆','消','✓','&#10003']): continue
                    h_name = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館|芝|ダ)', l)[0].strip()
                    if h_name: break

                # 最高・平均の抽出
                max_1y = int(re.search(r'最高\s*(\d+)', h_data).group(1)) if '最高' in h_data else 0
                avg_5 = int(re.search(r'5走平均\s*(\d+)', h_data).group(1)) if '5走平均' in h_data else 0
                
                # 過去走：前走(右端)から順にリスト化されるようパース
                runs = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?\s+([SMH]?)\s*(\d+)\s*\(([-0-9]+)\)', h_data)
                
                cands = []
                total_runs = len(runs)
                for j, (v, s, d, p, val, b_idx) in enumerate(runs):
                    if s != cur_s: continue
                    val_int = int(val)
                    adj = COURSE_MAP.get(s, {}).get(f"{v}{d}", 0)
                    penalty = 0
                    
                    # 近2走例外 (j=total_runs-1 が前走, j=total_runs-2 が2走前)
                    dist_from_latest = (total_runs - 1) - j
                    if dist_from_latest >= 2:
                        # 異常値 & 区分不一致
                        is_outlier = (max_1y - avg_5 >= 10) and (val_int == max_1y)
                        is_mismatch = check_mismatch(s, d, cur_s, cur_d)
                        if is_outlier or is_mismatch: penalty = -5
                    
                    cands.append(val_int + adj + penalty)
                
                ref = max(cands) if cands else max_1y
                linear = math.floor(60 + (ref - b_final))
                horses_list.append({'num': h_num, 'name': h_name, 'ref': ref, 'linear': linear, 'kei': linear})

            # C. 救済・ソート・出力
            if horses_list:
                # 参照指数降順で救済判定
                horses_list.sort(key=lambda x: x['ref'], reverse=True)
                for i in range(1, len(horses_list)):
                    p, c = horses_list[i-1], horses_list[i]
                    if (p['ref'] - c['ref'] <= 1) and (get_rank(p['linear']) != get_rank(c['linear'])) and (p['linear'] - c['linear'] < 3):
                        c['kei'], c['rank_up'] = p['kei'], True

                final_df = pd.DataFrame(horses_list).sort_values('num').reset_index(drop=True)
                final_df['rank'] = final_df['kei'].apply(get_rank)
                
                st.table(final_df[['num', 'name', 'ref', 'linear', 'kei', 'rank']])
                st.write("### スプレッドシート用 (TSV)")
                st.text_area("全選択してコピー", final_df[['num', 'name', 'ref', 'linear', 'kei', 'rank']].to_csv(sep='\t', index=False), height=200)
            else:
                st.error("馬のデータが見つかりませんでした。")
        except Exception as e:
            st.error(f"システムエラー: {e}")
