import streamlit as st
import pandas as pd
import random
import itertools

# 設定頁面配置
st.set_page_config(page_title="🏸 羽球公平排賽系統", page_icon="🏸", layout="wide")

# 初始化 Session State (用來儲存變數)
if 'players' not in st.session_state:
    # 格式: {'Name': {'games': 0, 'active': True}}
    st.session_state.players = {} 
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_matches' not in st.session_state:
    st.session_state.current_matches = []

# --- 核心邏輯函數 ---

def add_player(name):
    """新增玩家"""
    name = name.strip()
    if name and name not in st.session_state.players:
        st.session_state.players[name] = {'games': 0, 'active': True}
        return True
    return False

def remove_player(name):
    """移除玩家 (這會刪除數據，若只是暫離建議改用狀態切換)"""
    if name in st.session_state.players:
        del st.session_state.players[name]

def toggle_active(name):
    """切換玩家狀態 (在場/暫離)"""
    if name in st.session_state.players:
        st.session_state.players[name]['active'] = not st.session_state.players[name]['active']

def generate_matches(num_courts):
    """
    排賽演算法：
    1. 篩選出 'Active' 的玩家
    2. 優先選擇 '上場次數 (games)' 最少的人
    3. 若次數相同，則隨機排序以增加變化性
    """
    active_players = [name for name, data in st.session_state.players.items() if data['active']]
    
    # 檢查人數是否足夠
    needed = num_courts * 4
    if len(active_players) < 4:
        st.error(f"人數不足！至少需要 4 人才能開賽 (目前: {len(active_players)} 人)")
        return

    # 排序邏輯：先比上場次數(小到大)，次數相同則隨機洗牌
    # 這裡加入 random.random() 是為了讓同分的人每次排序不同
    ranked_players = sorted(active_players, key=lambda x: (st.session_state.players[x]['games'], random.random()))
    
    # 選出這一輪的玩家
    selected = ranked_players[:needed]
    
    # 隨機打亂這幾個人的配對 (這裡做簡單隨機，若要進階可加入不重複搭檔權重)
    random.shuffle(selected)
    
    matches = []
    # 每 4 人一組
    for i in range(0, len(selected), 4):
        if i + 3 < len(selected):
            match = {
                'court': (i // 4) + 1,
                'team1': [selected[i], selected[i+1]],
                'team2': [selected[i+2], selected[i+3]]
            }
            matches.append(match)
    
    st.session_state.current_matches = matches

def commit_round():
    """確認本輪結果，更新場次統計"""
    if not st.session_state.current_matches:
        return

    round_record = []
    for match in st.session_state.current_matches:
        p1, p2 = match['team1']
        p3, p4 = match['team2']
        
        # 更新上場次數
        st.session_state.players[p1]['games'] += 1
        st.session_state.players[p2]['games'] += 1
        st.session_state.players[p3]['games'] += 1
        st.session_state.players[p4]['games'] += 1
        
        round_record.append(f"Court {match['court']}: {p1}+{p2} vs {p3}+{p4}")

    st.session_state.history.append(round_record)
    st.session_state.current_matches = [] # 清空當前排程
    st.success("✅ 場次已記錄，次數已更新！")

# --- UI 介面設計 ---

st.title("🏸 羽球循環賽小幫手")

# 側邊欄：設定與人員管理
with st.sidebar:
    st.header("⚙️ 設定 & 人員")
    num_courts = st.number_input("場地數量", min_value=1, max_value=10, value=2)
    
    st.divider()
    
    # 新增玩家
    new_player = st.text_input("輸入名字後按 Enter 新增", placeholder="例如: 小明")
    if new_player:
        if add_player(new_player):
            st.toast(f"已新增: {new_player}")
        else:
            st.toast("名字重複或為空", icon="⚠️")

    st.divider()
    
    # 玩家列表管理
    st.subheader(f"玩家清單 ({len(st.session_state.players)}人)")
    
    # 轉成 DataFrame 方便顯示和操作
    if st.session_state.players:
        for name, data in st.session_state.players.items():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.write(f"**{name}** (打 {data['games']} 場)")
            with c2:
                # 狀態切換 (Active/Rest)
                active = st.checkbox("上場", value=data['active'], key=f"act_{name}", on_change=toggle_active, args=(name,))
            with c3:
                if st.button("❌", key=f"del_{name}"):
                    remove_player(name)
                    st.rerun()
    else:
        st.info("目前沒有玩家，請先新增。")
        # 快速測試按鈕
        if st.button("加入 14 位測試人員"):
            test_names = ["A倫", "B學", "C查", "D丹", "E伊", "F凡", "G吉", "H漢", "I艾", "J傑", "K凱", "L路", "M麥", "N尼"]
            for n in test_names:
                add_player(n)
            st.rerun()

# 主畫面
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📋 目前對戰組合")
    
    if st.session_state.current_matches:
        for match in st.session_state.current_matches:
            c_card = st.container(border=True)
            c_card.markdown(f"### 🏟️ 場地 {match['court']}")
            c_a, c_vs, c_b = c_card.columns([4, 1, 4])
            with c_a:
                st.info(f"{match['team1'][0]} & {match['team1'][1]}")
            with c_vs:
                st.markdown("<h3 style='text-align: center'>VS</h3>", unsafe_allow_html=True)
            with c_b:
                st.warning(f"{match['team2'][0]} & {match['team2'][1]}")
        
        if st.button("✅ 這輪打完了 (更新數據)", type="primary", use_container_width=True):
            commit_round()
            st.rerun()
    else:
        st.info("尚未產生對戰，請點擊下方按鈕。")
        if st.button("🎲 產生下一輪對戰", type="primary", use_container_width=True):
            generate_matches(num_courts)
            st.rerun()

with col2:
    st.subheader("📊 休息區 / 等候名單")
    active_p = [p for p, d in st.session_state.players.items() if d['active']]
    
    # 找出目前沒在打球的人
    playing_now = []
    if st.session_state.current_matches:
        for m in st.session_state.current_matches:
            playing_now.extend(m['team1'])
            playing_now.extend(m['team2'])
            
    waiting = [p for p in active_players if p not in playing_now] if 'active_players' in locals() else []
    # 修正變數範圍問題，重新計算
    all_active = [n for n, d in st.session_state.players.items() if d['active']]
    waiting = [p for p in all_active if p not in playing_now]
    
    if waiting:
        for p in waiting:
            st.text(f"💤 {p} (已打 {st.session_state.players[p]['games']} 場)")
    else:
        st.write("目前無人休息")

    st.divider()
    st.subheader("📜 歷史紀錄")
    for i, r in enumerate(reversed(st.session_state.history)):
        with st.expander(f"第 {len(st.session_state.history)-i} 輪"):
            for game in r:
                st.write(game)