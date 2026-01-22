import streamlit as st
import random

# 設定頁面配置
st.set_page_config(page_title="🏸 羽球非同步輪替系統", page_icon="🏸", layout="wide")

import json
import os

DATA_FILE = "badminton_state.json"

def save_state():
    """儲存目前狀態到 JSON"""
    data = {
        "players": st.session_state.players,
        "courts": st.session_state.courts,
        "courts": st.session_state.courts,
        "court_status": st.session_state.court_status, # NEW: Save status
        "history": st.session_state.history
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_state():
    """從 JSON 讀取狀態"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state.players = data.get("players", {})
                
                # JSON key 雖然存成字串，讀回來要轉回 int key
                raw_courts = data.get("courts", {})
                st.session_state.courts = {int(k): v for k, v in raw_courts.items()}
                
                # Load status
                raw_status = data.get("court_status", {})
                st.session_state.court_status = {int(k): v for k, v in raw_status.items()}

                st.session_state.history = data.get("history", [])
            return True
        except Exception as e:
            st.error(f"讀取存檔失敗: {e}")
    return False

# --- 初始化 Session State ---
if 'initialized' not in st.session_state:
    # 嘗試讀取存檔
    if load_state():
        st.toast("已恢復上次的狀態", icon="📂")
    st.session_state.initialized = True

if 'players' not in st.session_state:
    # 玩家資料庫：{'Name': {'games': 0, 'active': True}}
    st.session_state.players = {} 
if 'courts' not in st.session_state:
    # 場地狀態：{1: [], 2: []} -> 存該場地目前的玩家名單，若為空代表閒置
    # 預設先開 2 個
    st.session_state.courts = {1: [], 2: []}
if 'court_status' not in st.session_state:
    # 場地狀態：{1: "EDITING", 2: "PLAYING"}
    st.session_state.court_status = {1: "EDITING", 2: "EDITING"}
if 'history' not in st.session_state:
    st.session_state.history = []
if 'enable_balancing' not in st.session_state:
    st.session_state.enable_balancing = True

# --- 核心邏輯函數 ---

def add_player(name, level="有點累組"):
    """新增玩家"""
    name = name.strip()
    if name and name not in st.session_state.players:
        st.session_state.players[name] = {
            'games': 0, 
            'active': True,
            'level': level
        }
        save_state()
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
        save_state()

def toggle_active(name):
    """切換玩家狀態"""
    if name in st.session_state.players:
        st.session_state.players[name]['active'] = not st.session_state.players[name]['active']
        save_state()

def balance_teams(players):
    """
    將 4 位玩家分成兩隊，使雙方實力最接近
    Level weights: 死亡之組=3, 有點累組=2, 休閒組=1
    """
    if not st.session_state.get('enable_balancing', True):
        # 如果關閉平衡，則隨機打亂後直接分隊 (前2人一隊，後2人一隊)
        p = list(players)
        random.shuffle(p)
        return p

    weights = {"死亡之組": 3, "有點累組": 2, "休閒組": 1}
    
    def get_score(p_name):
        lv = st.session_state.players[p_name].get('level', '有點累組')
        return weights.get(lv, 2)

    # 4 players: p0, p1, p2, p3
    # Combinations:
    # 1. (p0, p1) vs (p2, p3)
    # 2. (p0, p2) vs (p1, p3)
    # 3. (p0, p3) vs (p1, p2)
    
    best_diff = float('inf')
    best_combo = players # default
    
    # itertools.combinations is good, but hardcoded is faster for 4 items
    # Let's fix p0 as the pivot for the first team
    p0 = players[0]
    others = players[1:]
    
    import itertools
    # pairs for p0:
    for i in range(3):
        partner = others[i]
        opponents = [x for x in others if x != partner]
        
        team1 = [p0, partner]
        team2 = opponents
        
        score1 = get_score(team1[0]) + get_score(team1[1])
        score2 = get_score(team2[0]) + get_score(team2[1])
        
        diff = abs(score1 - score2)
        
        if diff < best_diff:
            best_diff = diff
            # Shuffle within teams for randomness
            random.shuffle(team1)
            random.shuffle(team2)
            # Random side assignment
            if random.random() > 0.5:
                best_combo = team1 + team2
            else:
                best_combo = team2 + team1
        elif diff == best_diff:
            # If equal, 50% chance to switch to this one to keep variety
            if random.random() > 0.5:
                random.shuffle(team1)
                random.shuffle(team2)
                if random.random() > 0.5:
                    best_combo = team1 + team2
                else:
                    best_combo = team2 + team1

    return best_combo

def get_next_players(exclude_players, count=4):
    """
    從休息區挑選下一組人 (考慮實力分組)
    exclude_players: 目前正在其他場地打球的人
    """
    # 1. 找出候選人
    candidates = [
        p for p, data in st.session_state.players.items() 
        if data['active'] and p not in exclude_players
    ]
    
    # 這裡的邏輯需要改變：
    # 我們不能只是簡單排序，還需要檢查相容性。
    # 規則：死亡之組與休閒組不共存。
    
    # helper: 檢查一群是否相容 compatible
    def is_compatible(group_names):
        levels = {st.session_state.players[n].get('level', '有點累組') for n in group_names}
        if "死亡之組" in levels and "休閒組" in levels:
            return False
        return True



    # 排序策略：場次少 -> 隨機
    ranked = sorted(candidates, key=lambda x: (st.session_state.players[x]['games'], random.random()))
    
    if len(ranked) < count:
        return None

    # Greedy Attempt:
    # 直接取前 count 個，如果不相容，就從第 count+1 個開始嘗試替換掉不相容的成員...
    # 但這樣寫比較複雜。
    # 簡單做法：
    # 嘗試以 priority 最高的當 core，然後去拉相容的人。
    
    # 定義每個人的 Level Weight 以便過濾? 不需要，直接檢查字串
    
    # 迭代每一個高優先級的人作為「種子(Seed)」
    # 為了避免 O(N!)，我們只嘗試以 sorted list 的前幾名作為種子
    
    for i in range(len(ranked)):
        seed = ranked[i]
        valid_group = [seed]
        
        # 嘗試從剩下的人裡抓 3 個
        # 為了保持場次公平，我們依照 ranked 順序去檢查
        for other in ranked:
            if other == seed: continue
            
            # 檢查加入 other 後是否仍相容
            # 由於我們只檢查是否同時存在死亡和休閒
            # 所以只要 group + other 不違反即可
            temp_group = valid_group + [other]
            if is_compatible(temp_group):
                valid_group.append(other)
            
            if len(valid_group) == count:
                # 找到了!
                # 再次隨機打亂這組
                return balance_teams(valid_group)
    
    return None # 找不到組合

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
        st.session_state.court_status[court_id] = "EDITING" # New group starts in editing mode
        st.toast(f"場地 {court_id} 更新完畢！", icon="✅")
        save_state()
    else:
        st.warning("休息區人數不足 4 人，無法自動排下一場，請等待其他場地結束。")

def reset_court(court_id):
    """手動清空場地（不結算成績）"""
    st.session_state.courts[court_id] = []
    st.session_state.court_status[court_id] = "EDITING"
    save_state()

def remove_player_from_court(court_id, player_name):
    """從場地移除玩家 (回到休息區)"""
    if player_name in st.session_state.courts[court_id]:
        st.session_state.courts[court_id].remove(player_name)
        save_state()

def start_game(court_id):
    """鎖定場地，開始比賽 (並執行戰力平衡)"""
    players = st.session_state.courts[court_id]
    if len(players) == 4:
        # Final balance
        balanced = balance_teams(players)
        st.session_state.courts[court_id] = balanced
        st.session_state.court_status[court_id] = "PLAYING"
        save_state()
        st.toast(f"場地 {court_id} 比賽開始！(已平衡戰力)")
    else:
        st.warning("人數不足 4 人，無法開始")

def manual_add_player(name):
    """手動將休息區玩家加入第一個有空位的場地 (隨機/依序填補)"""
    # 找尋第一個未滿的場地
    target_court = None
    # 動態取得目前所有場地 ID
    active_courts = sorted(st.session_state.courts.keys())
    for cid in active_courts: 
        if len(st.session_state.courts[cid]) < 4:
            target_court = cid
            break
            
    if target_court:
        st.session_state.courts[target_court].append(name)
        # 如果使用者想要「隨機位置」，可以在這裡 shuffle，但通常填補順序沒差，
        # 等滿 4 人再 shuffle 或是依加入順序排。
        # 這裡單純 append。
        st.toast(f"已將 {name} 加入場地 {target_court}")
        save_state()
        return True
    else:
        st.warning("所有場地已滿！")
        return False

# --- UI 介面 ---

st.title("🏸 羽球即時輪替看板 (FIFO模式)")

# --- 頁面導航 ---
page = st.sidebar.radio("📍 選單", ["🏸 排程看板", "📘 使用說明 & 演算法"], index=0)

if page == "📘 使用說明 & 演算法":
    st.header("📘 系統使用說明")
    st.markdown("""
    ### 1. 核心功能
    因為抽籤分組太麻煩了，所以寫了一套分組系統測試看看能不能增加分組效率，這套系統可以確保每個人上場次數盡量平均。
戰力分組功能還在測試中)戰力分組功能還在測試中))
    ### 2. 操作流程
    1.  **新增球員**：在左側欄位輸入名字並選擇分組等級。
    2.  **管理狀態**：
        -   ✅ **勾選**：代表目前在場邊等待或打球中（Active）。
        -   ⬜ **取消勾選**：代表暫時離開或休息（不會被排入下一場）。
    3.  **場地運作 (兩階段模式)**：
        -   ✏️ **編輯模式 (Editing)**：
            -   場地空白或剛換人時。
            -   你可以手動從下方休息區點擊 `➕` 加入特定人員。
            -   也可以點擊場地上的 `❌` 將人移除。
        -   🔒 **對戰模式 (Playing)**：
            -   當場地滿 4 人後，點擊 **「🚀 開始對戰」**。
            -   系統會**鎖定場地**，並自動執行 **「戰力平衡演算法」(測試版本)** 分隊。
    4.  **結束換場**：
        -   比賽結束後，點擊 **「⏱️ 結束 & 換下一組」**。
        -   系統會記錄場次，並自動從休息區挑選「打最少場」的人遞補。

    ---

    ### 🧠 演算法細節 (Algorithm)

    #### 1. 優先配對邏輯 (Matchmaking)
    系統如何挑選下一組上場的人？
    -   **Rule 1 - 公平性**：永遠優先挑選 **「上場次數最少」** 的球員。
    -   **Rule 2 - 隨機性**：若多人場次相同，則隨機挑選，避免固定順位。
    -   **Rule 3 - 分組相容性(測試版本)**：
        -   系統建有防呆機制，避免讓 **「死亡之組 (Pro)」** 與 **「休閒組 (Casual)」** 出現在同一場，以免雙方都打得不盡興。

    #### 2. 戰力平衡邏輯 (Team Balancing)(測試版本)
    當 4 個人選定後，系統如何分隊？
    -   系統利用 **權重計算** 來尋找最勢均力敵的組合。
    -   **權重設定**：
        -   💀 **死亡之組**: 3 分
        -   😓 **有點累組**: 2 分
        -   ☕ **休閒組**: 1 分
    -   **運算過程**：
        1.  計算 4 人所有可能的分隊組合 (A+B vs C+D, A+C vs B+D, ...)。
        2.  計算每隊的總權重分 (例如：死亡+休閒 = 3+1 = 4)。
        3.  選擇 **「兩隊分差最小」** 的組合。
        -   *例如：(高手+新手) vs (中手+中手) 往往比 (高手+中手) vs (中手+新手) 更公平。*
    """)
    st.stop() # 停止執行後續的 Dashboard 程式碼

# 側邊欄：設定
with st.sidebar:
    st.header("⚙️ 設定 & 人員管理")
    
    # --- 場地數量設定 ---
    current_court_num = len(st.session_state.courts)
    selected_court_num = st.radio("場地數量", [1, 2], index=1 if current_court_num >= 2 else 0, horizontal=True)
    
    # --- 戰力平衡設定 ---
    st.session_state.enable_balancing = st.toggle("啟用戰力平衡 (分組優化)", value=st.session_state.get('enable_balancing', True))
    
    if selected_court_num != current_court_num:
        # 更新場地字典
        if selected_court_num > current_court_num:
            # 增加場地
            for i in range(current_court_num + 1, selected_court_num + 1):
                st.session_state.courts[i] = []
                st.session_state.court_status[i] = "EDITING"
        else:
            # 減少場地 (移除 ID 較大的)
            for i in range(current_court_num, selected_court_num, -1):
                if i in st.session_state.courts:
                    del st.session_state.courts[i]
                    if i in st.session_state.court_status:
                        del st.session_state.court_status[i]
        save_state()
        st.rerun() # 重整以更新介面
    
    st.divider()
    
    st.subheader("人員新增")
    
    new_name = st.text_input("名字", placeholder="輸入名字...")
    new_level = st.selectbox("分組", ["死亡之組", "有點累組", "休閒組"], index=1)
    if st.button("新增"):
        if add_player(new_name, new_level): 
            st.toast(f"已新增 {new_name} ({new_level})")


    st.divider()
    
    # 快速建立測試資料
    if not st.session_state.players:
        if st.button("加入寶可夢測試員"):
            pokemon_roster = [
                ("超夢", "死亡之組"), ("快龍", "死亡之組"), ("烈空座", "死亡之組"), ("班基拉斯", "死亡之組"),
                ("噴火龍", "有點累組"), ("路卡利歐", "有點累組"), ("耿鬼", "有點累組"), ("怪力", "有點累組"), ("皮卡丘", "有點累組"),
                ("鯉魚王", "休閒組"), ("可達鴨", "休閒組"), ("呆呆獸", "休閒組"), ("胖丁", "休閒組"), ("百變怪", "休閒組")
            ]
            import random
            # 隨機挑選 10-12 隻加入
            selected = random.sample(pokemon_roster, 12)
            
            for name, level in selected: 
                add_player(name, level)
            st.rerun()

    st.write("勾選 = 可上場 / 取消 = 暫離")
    
    # 玩家列表
    # 轉成列表並排序(顯示用)
    sorted_players = sorted(st.session_state.players.items(), key=lambda x: -x[1]['games'])
    
    for name, data in sorted_players:
        c1, c2, c3 = st.columns([5, 1, 1])
        with c1:
            lv_icon = {"死亡之組": "💀", "有點累組": "😓", "休閒組": "☕"}.get(data.get('level'), "😓")
            st.write(f"**{name}** {lv_icon} ({data['games']}場)")
        with c2:
            st.checkbox("", value=data['active'], key=f"act_{name}", on_change=toggle_active, args=(name,))
        with c3:
            if st.button("x", key=f"del_{name}"):
                remove_player(name)
                st.rerun()

    if st.button("🗑️ 清除所有紀錄 (重置)", type="primary"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.session_state.clear()
        st.rerun()

# 主畫面：場地顯示區
st.subheader("🏟️ 場地現況")

# 動態生成場地卡片
active_courts = sorted(st.session_state.courts.keys())
court_cols = st.columns(len(active_courts)) 

for i, court_id in enumerate(active_courts): 
    with court_cols[i]:
        container = st.container(border=True)
        container.markdown(f"### 🏸 場地 {court_id}")
        
        current_p = st.session_state.courts[court_id]
        

        
        # 確保 status 存在 (防錯)
        c_status = st.session_state.court_status.get(court_id, "EDITING")

        # Helper to format player with level
        def fmt_p(name):
            if name == "waiting...": return name
            # Handle case where player might have been deleted but still on court (edge case)
            p_data = st.session_state.players.get(name)
            if not p_data: return name
            
            lv = p_data.get('level', '')
            icon = {"死亡之組": "💀", "有點累組": "😓", "休閒組": "☕"}.get(lv, "")
            return f"{name} {icon}"

        if current_p:
            # --- PLAYING 狀態 ---
            if c_status == "PLAYING":
                # 補齊 4 個位置以便顯示 (用空字串佔位)
                display_p = current_p + ["waiting..."] * (4 - len(current_p))
                
                # Apply formatting
                d_p = [fmt_p(x) for x in display_p]

                # 顯示對戰陣容
                c_team1, c_vs, c_team2 = container.columns([2,1,2])
                with c_team1:
                    st.info(f"{d_p[0]}\n\n{d_p[1]}")
                with c_vs:
                    st.markdown("<br><div style='text-align: center'>VS</div>", unsafe_allow_html=True)
                with c_team2:
                    st.error(f"{d_p[2]}\n\n{d_p[3]}")
                
                # 按鈕：結束這場並換下一組
                if container.button(f"⏱️ 結束 & 換下一組", key=f"next_{court_id}", type="primary", use_container_width=True):
                    finish_and_next(court_id)
                    st.rerun()
                    
            # --- EDITING 狀態 ---
            else:
                st.caption("調整中 (點擊 ❌ 可移除)")
                # 顯示目前名單 + 移除按鈕
                for p in current_p:
                    # 使用 columns 讓移除按鈕排在名字旁邊
                    ec1, ec2 = container.columns([4, 1])
                    ec1.write(f"👤 {fmt_p(p)}")
                    if ec2.button("❌", key=f"rm_{court_id}_{p}"):
                        remove_player_from_court(court_id, p)
                        st.rerun()
                
                # 補位提示
                if len(current_p) < 4:
                    container.info(f"等待加入... ({len(current_p)}/4)")
                else:
                    # 滿 4 人 -> 顯示開始按鈕
                    if container.button("🚀 開始對戰 (鎖定)", key=f"start_game_{court_id}", type="primary", use_container_width=True):
                        start_game(court_id)
                        st.rerun()

            # 共用：清除按鈕
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
        st.caption("點擊按鈕可手動加入場地")
        for p in waiting_sorted:
            # 準備顯示資訊
            d = st.session_state.players[p]
            lv = d.get('level', '有點累組')
            icon = {"死亡之組": "💀", "有點累組": "😓", "休閒組": "☕"}.get(lv, "😓")
            
            # 使用 callback 處理點擊
            if st.button(f"➕ {p} {icon} ({d['games']}場)", key=f"btn_add_{p}"):
                 manual_add_player(p)
                 st.rerun()
    else:
        st.write("無人休息")

with c_hist:
    st.subheader("📜 對戰紀錄")
    for rec in st.session_state.history[:10]: # 只顯示最近 10 筆
        st.text(rec)