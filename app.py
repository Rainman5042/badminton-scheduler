import streamlit as st
import random

# 設定頁面配置
st.set_page_config(page_title="🏸 羽球非同步輪替系統", page_icon="🏸", layout="wide")

# --- 初始化 Session State ---
if 'players' not in st.session_state:
    # 玩家資料庫：{'Name': {'games': 0, 'active': True}}
    st.session_state.players = {} 
if 'courts' not in st.session_state:
    # 場地狀態：{1: [], 2: []} -> 存該場地目前的玩家名單，若為空代表閒置
    st.session_state.courts = {1: [], 2: []}
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 核心邏輯函數 ---

def add_player(name):
    """新增玩家"""
    name = name.strip()
    if name and name not in st.session_state.players:
        st.session_state.players[name] = {'games': 0, 'active': True}
        return True
    return False

def remove_player(name):
    """移除玩家"""
    if name in st.session_state.players:
        # 如果玩家正在場上，強制清空該場地以免出錯
        for c_id, p_list in st.session_state.courts.items():
            if name in p_list:
                st.session_state.courts[c_id] = []
        del st.session_state.players[name]

def toggle_active(name):
    """切換玩家狀態"""
    if name in st.session_state.players:
        st.session_state.players[name]['active'] = not st.session_state.players[name]['active']

def get_next_players(exclude_players, count=4):
    """
    從休息區挑選下一組人
    exclude_players: 目前正在其他場地打球的人（不能被選）
    """
    # 1. 找出所有 Active 且 不在場上 的人
    candidates = [
        p for p, data in st.session_state.players.items() 
        if data['active'] and p not in exclude_players
    ]
    
    if len(candidates) < count:
        return None  # 人數不足
    
    # 2. 排序策略：優先選「場次少」的 -> 其次隨機 (避免同分時總是同一批人)
    # random.random() 作為第二排序鍵，確保同分時隨機
    ranked = sorted(candidates, key=lambda x: (st.session_state.players[x]['games'], random.random()))
    
    # 3. 選出前 4 名
    selected = ranked[:count]
    
    # 4. 隨機分隊 (Team A vs Team B)
    random.shuffle(selected)
    return selected

def finish_and_next(court_id):
    """
    按下「結束並換場」時的邏輯：
    1. 結算舊成績 (場次+1)
    2. 釋放舊球員到休息區
    3. 立刻從休息區抓新的一組人上場
    """
    # --- 步驟 1: 結算舊場次 ---
    current_players = st.session_state.courts[court_id]
    if current_players:
        # 記錄歷史
        record = f"場地 {court_id}: {current_players[0]}+{current_players[1]} vs {current_players[2]}+{current_players[3]}"
        st.session_state.history.insert(0, record) # 新的插在最前面
        
        # 更新場次數
        for p in current_players:
            if p in st.session_state.players:
                st.session_state.players[p]['games'] += 1
    
    # 清空該場地，讓這些人變成「候選人」
    st.session_state.courts[court_id] = []
    
    # --- 步驟 2: 找出誰還在「其他」場地上 (這些人不能選) ---
    busy_players = []
    for c_id, p_list in st.session_state.courts.items():
        if c_id != court_id and p_list: # 別的場地且有人
            busy_players.extend(p_list)
            
    # --- 步驟 3: 產生新對戰 ---
    next_group = get_next_players(exclude_players=busy_players, count=4)
    
    if next_group:
        st.session_state.courts[court_id] = next_group
        st.toast(f"場地 {court_id} 更新完畢！", icon="✅")
    else:
        st.warning("休息區人數不足 4 人，無法自動排下一場，請等待其他場地結束。")

def reset_court(court_id):
    """手動清空場地（不結算成績）"""
    st.session_state.courts[court_id] = []

# --- UI 介面 ---

st.title("🏸 羽球即時輪替看板 (FIFO模式)")

# 側邊欄：設定
with st.sidebar:
    st.header("⚙️ 人員管理")
    
    # 快速建立測試資料
    if not st.session_state.players:
        if st.button("一鍵加入 14 位測試員"):
            names = ["A倫", "B學", "C查", "D丹", "E伊", "F凡", "G吉", "H漢", "I艾", "J傑", "K凱", "L路", "M麥", "N尼"]
            for n in names: add_player(n)
            st.rerun()

    new_player = st.text_input("新增玩家", placeholder="輸入名字...")
    if new_player:
        if add_player(new_player): st.toast(f"已新增 {new_player}")

    st.divider()
    st.write("勾選 = 可上場 / 取消 = 暫離")
    
    # 玩家列表
    # 轉成列表並排序(顯示用)
    sorted_players = sorted(st.session_state.players.items(), key=lambda x: -x[1]['games'])
    
    for name, data in sorted_players:
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            st.write(f"**{name}** ({data['games']}場)")
        with c2:
            st.checkbox("", value=data['active'], key=f"act_{name}", on_change=toggle_active, args=(name,))
        with c3:
            if st.button("x", key=f"del_{name}"):
                remove_player(name)
                st.rerun()

# 主畫面：場地顯示區
st.subheader("🏟️ 場地現況")

# 動態生成場地卡片
court_cols = st.columns(2) # 預設兩欄，兩個場地

for i, court_id in enumerate([1, 2]): # 這裡預設 2 個場地，可依需求擴充
    with court_cols[i]:
        container = st.container(border=True)
        container.markdown(f"### 🏸 場地 {court_id}")
        
        current_p = st.session_state.courts[court_id]
        
        if current_p:
            # 顯示對戰陣容
            c_team1, c_vs, c_team2 = container.columns([2,1,2])
            with c_team1:
                st.info(f"{current_p[0]}\n\n{current_p[1]}")
            with c_vs:
                st.markdown("<br><div style='text-align: center'>VS</div>", unsafe_allow_html=True)
            with c_team2:
                st.error(f"{current_p[2]}\n\n{current_p[3]}")
            
            # 按鈕：結束這場並換下一組
            if container.button(f"⏱️ 結束 & 換下一組", key=f"next_{court_id}", type="primary", use_container_width=True):
                finish_and_next(court_id)
                st.rerun()
                
            # 小按鈕：只清空不結算
            if container.button("清除", key=f"cls_{court_id}"):
                reset_court(court_id)
                st.rerun()
        else:
            # 場地目前是空的
            container.write("❌ 目前空場")
            
            # 計算如果現在開局，誰會上場
            busy = []
            for c, p in st.session_state.courts.items():
                if p: busy.extend(p)
            
            # 預覽下一組
            preview = get_next_players(busy, 4)
            if preview:
                container.caption(f"預計下組: {','.join(preview)}")
                if container.button("🚀 開始安排", key=f"start_{court_id}", type="primary", use_container_width=True):
                    # 手動觸發一次「結束並換場」邏輯(雖然沒舊人，但邏輯通)
                    finish_and_next(court_id)
                    st.rerun()
            else:
                container.warning("休息區人數不足")

# 底部資訊：休息區 & 歷史
st.divider()
c_rest, c_hist = st.columns([1, 1])

with c_rest:
    st.subheader("💤 休息中 / 等候區")
    # 找出所有在場上的人
    on_court = []
    for p_list in st.session_state.courts.values():
        on_court.extend(p_list)
    
    # 篩選出 active 但不在場上的人
    waiting = [p for p, d in st.session_state.players.items() if d['active'] and p not in on_court]
    # 依照場次由少到多排序 (顯示誰是下一順位)
    waiting_sorted = sorted(waiting, key=lambda x: (st.session_state.players[x]['games'], random.random()))
    
    if waiting_sorted:
        st.write(f"目前 {len(waiting_sorted)} 人候位（依優先順序排列）：")
        for p in waiting_sorted:
            st.code(f"{p} (已打 {st.session_state.players[p]['games']} 場)")
    else:
        st.write("無人休息")

with c_hist:
    st.subheader("📜 對戰紀錄")
    for rec in st.session_state.history[:10]: # 只顯示最近 10 筆
        st.text(rec)