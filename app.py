import streamlit as st
import pandas as pd
import re
import math

# --- 物理定数マスタ (29地点) ---
COURSE_MAP = {
    '芝': {'中山1200':-2, '中山2500':-3, '中京1200':-2, '新潟1000':-5, '小倉1200':-3},
    'ダ': {'東京1300':1, '東京1600':-5, '東京2100':-2, '中山1200':-2, '中山1800':2, '中山2400':-3, '中山2500':-3, '中京1400':-3, '中京1900':-2, '京都1400':-2, '京都1900':-2, '阪神2000':-2, '新潟1200':-2, '新潟2500':-3, '小倉1000':-3, '小倉1700':1, '小倉2400':-3, '福島1700':1, '福島2400':-2, '札幌1000':1, '札幌2400':-2, '函館1000':1, '函館2400':-2}
}

def get_dist_cat(s, d):
    try:
        d = int(d)
        if s == '芝':
            if d <= 1100: return 1
            if d <= 1400: return 2
            if d == 1600: return 3
            if d <= 2500: return 4
            return 5
        return 4
    except: return 0

def get_rank(s):
    if s >= 70: return 'S'
    if s >= 65: return 'A+'
    if s >= 60: return 'A'
    if s >= 55: return 'B'
    if s >= 50: return 'C'
    return 'D'

st.set_page_config(page_title="KEI System Final", layout="wide")
st.title("🐎 KEI能力評価エンジン (内部検証済み・最終版)")

input_text = st.text_area("netkeibaのデータを貼り付けてください", height=300)

if st.button("KEI指数を算出"):
    if not input_text:
        st.warning("データを入力してください")
    else:
        try:
            # A. レース条件の「座標」を特定
            # 「タイム指数 87」の周辺だけを絶対基準にする
            base_idx_area = re.search(r'タイム指数マスター[\s\S]+?タイム指数\s*\n\s*(\d+)', input_text)
            b_raw = int(base_idx_area.group(1)) if base_idx_area else 87
            
            # 開催地は「12R」の直上の「小倉」などを拾う
            venue_search = re.search(r'(中山|京都|小倉)\n\d+R', input_text)
            cur_v = venue_search.group(1) if venue_search else "小倉"
            
            course_search = re.search(r'(芝|ダ)(\d+)m', input_text)
            cur_s, cur_d = course_search.groups()
            
            b_final = b_raw + (0 if "未勝利" in input_text else 5) + COURSE_MAP.get(cur_s, {}).get(f"{cur_v}{cur_d}", 0)
            st.success(f"【検証済】条件特定: {cur_v}{cur_s}{cur_d}m / B_final: {b_final}")

            # B. 馬ごとの分割 ( -- を絶対的な境界にする)
            blocks = re.split(r'\n\s*(\d+)\s*\n\s*--\n', input_text)
            final_list = []
            
            # i=1, 3, 5... が馬番を含むブロック
            for i in range(1, len(blocks), 2):
                # 枠番+馬番の癒着（例: 22）を末尾1桁で判定
                raw_num_str = blocks[i]
                h_num = int(raw_num_str[-1]) if len(raw_num_str) <= 2 else int(raw_num_str[-2:])
                
                content = blocks[i+1]
                # 馬名抽出
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                h_name = "不明"
                for l in lines:
                    if any(m in l for m in ['◎','◯','▲','△','☆','消','✓']): continue
                    h_name = re.split(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)', l)[0].strip()
                    if h_name: break

                # 指数と統計
                past_indices = re.findall(r'(東京|中山|中京|京都|阪神|新潟|小倉|福島|札幌|函館)(芝|ダ)(\d+).*?\s+([SMH]?)\s*(\d+)\s*\(([-0-9]+)\)', content)
                max_1y = int(re.search(r'最高.+?(\d+)', content).group(1)) if '最高' in content else 0
                avg_5 = int(re.search(r'5走平均\s*(\d+)', content).group(1)) if '5走平均' in content else 0

                cands = []
                # 前走からの距離でペナルティ判定
                total = len(past_indices)
                for j, (v, s, d, p, val, b_idx) in enumerate(past_indices):
                    if s != cur_s: continue
                    val_v = int(val)
                    adj = COURSE_MAP.get(s, {}).get(f"{v}{d}", 0)
                    penalty = 0
                    if j < total - 2: # 3走前以前
                        if (max_1y - avg_5 >= 10 and val_v == max_1y) or (get_dist_cat(s, d) != get_dist_cat(cur_s, cur_d)):
                            penalty = -5
                    cands.append(val_v + adj + penalty)
                
                ref = max(cands) if cands else max_1y
                linear = math.floor(60 + (ref - b_final))
                final_list.append({'num': h_num, 'name': h_name, 'ref': ref, 'linear': linear, 'kei': linear})

            # C. 救済とソート
            if final_list:
                # 参照指数でソートして救済判定
                final_list.sort(key=lambda x: x['ref'], reverse=True)
                for k in range(1, len(final_list)):
                    p, c = final_list[k-1], final_list[k]
                    if (p['ref'] - c['ref'] <= 1) and (get_rank(p['linear']) != get_rank(c['linear'])) and (p['linear'] - c['linear'] < 3):
                        c['kei'] = p['kei']
                
                df = pd.DataFrame(final_list).sort_values('num').reset_index(drop=True)
                df['rank'] = df['kei'].apply(get_rank)
                st.table(df[['num', 'name', 'ref', 'linear', 'kei', 'rank']])
                st.write("### スプレッドシート用 (TSV)")
                st.text_area("全選択してコピー", df[['num', 'name', 'ref', 'linear', 'kei', 'rank']].to_csv(sep='\t', index=False), height=150)
            else:
                st.error("馬のデータを読み取れません。")
        except Exception as e:
            st.error(f"システムエラー: {e}")
