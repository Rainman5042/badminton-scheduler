import streamlit as st
import random
import json
import os
import base64
from openai import OpenAI

# 設定頁面配置
st.set_page_config(page_title="🏸 羽球非同步輪替系統", page_icon="🏸", layout="wide")

# --- 讀取 API Key ---
# 優先從 Streamlit Secrets 讀取
api_key = st.secrets.get("OPENAI_API_KEY", None)

DATA_FILE = "badminton_state.json"

def save_state():
    """儲存目前狀態到 JSON"""
    data = {
        "players": st.session_state.players,
        "courts": st.session_state.courts,
        "court_status": st.session_state.court_status,
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
    if load_state():
        st.toast("已恢復上次的狀態", icon="📂")
    st.session_state.initialized = True

if 'players' not in st.session_state:
    st.session_state.players = {} 
if 'courts' not in st.session_state:
    st.session_state.courts = {1: [], 2: []}
if 'court_status' not in st.session_state:
    st.session_state.court_status = {1: "EDITING", 2: "EDITING"}
if 'history' not in st.session_state:
    st.session_state.history = []
if 'enable_balancing' not in st.session_state:
    st.session_state.enable_balancing = True
if 'ocr_results' not in st.session_state:
    st.session_state.ocr_results = [] 

# --- OpenAI Vision 處理函數 ---

def process_image_with_openai(uploaded_file):
    """使用 OpenAI GPT-4o 辨識圖片中的人員名單"""
    if not api_key:
        st.error("找不到 API Key！請在 Streamlit Community Cloud 的 Settings > Secrets 中設定 OPENAI_API_KEY。")
        return []

    try:
        # 將圖片轉為 Base64
        base64_image = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
        
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o", # 使用具備視覺能力的模型
            messages=[
                {
                    "role": "system",
                    "content": "你是一個協助整理名單的助手。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "請辨識這張 Line 投票截圖中的人員名單。請忽略時間、電量、'打'、'不打'等標題文字。只回傳名字列表，一行一個名字。不要包含編號或任何 Markdown 符號。"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        # 處理回傳的文字 (分割換行)
        names = [line.strip() for line in content.split('\n') if line.strip()]
        return names

    except Exception as e:
        st.error(f"OpenAI API 呼叫失敗: {e}")
        return []

# --- 核心邏輯函數 ---

def add_player(name, level="有點累組"):
    name = name.strip()
    if len(name) < 1: return False
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
    if name in st.session_state.players:
        for c_id, p_list in st.session_state.courts.items():
            if name in p_list:
                st.session_state.courts[c_id] = []
        del st.session_state.players[name]
        save_state()

def edit_player(old_name, new_name, new_level, new_games):
    """編輯玩家資料"""
    # 1. 如果名字沒變，只更新屬性
    if old_name == new_name:
        if old_name in st.session_state.players:
            st.session_state.players[old_name]['level'] = new_level
            st.session_state.players[old_name]['games'] = new_games
            save_state()
            return True
    else:
        # 2. 如果名字變了 (相當於改名)
        # 檢查新名字是否衝突
        if new_name in st.session_state.players:
            st.error(f"名字 {new_name} 已存在！")
            return False
            
        if old_name in st.session_state.players:
            # 複製舊資料但更新屬性
            data = st.session_state.players[old_name]
            data['level'] = new_level
            data['games'] = new_games
            
            # 建立新 key
            st.session_state.players[new_name] = data
            
            # 刪除舊 key
            del st.session_state.players[old_name]
            
            # 更新場地上的名字 (如果他在場上)
            for c_id, p_list in st.session_state.courts.items():
                if old_name in p_list:
                    # 找到並替換
                    idx = p_list.index(old_name)
                    p_list[idx] = new_name
            
            save_state()
            return True
    return False

def toggle_active(name):
    if name in st.session_state.players:
        st.session_state.players[name]['active'] = not st.session_state.players[name]['active']
        save_state()

def balance_teams(players):
    if not st.session_state.get('enable_balancing', True):
        p = list(players)
        random.shuffle(p)
        return p

    weights = {"死亡之組": 3, "有點累組": 2, "休閒組": 1}
    
    def get_score(p_name):
        lv = st.session_state.players[p_name].get('level', '有點累組')
        return weights.get(lv, 2)

    p0 = players[0]
    others = players[1:]
    
    best_diff = float('inf')
    best_combo = players 
    
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
            random.shuffle(team1)
            random.shuffle(team2)
            if random.random() > 0.5:
                best_combo = team1 + team2
            else:
                best_combo = team2 + team1
        elif diff == best_diff:
            if random.random() > 0.5:
                random.shuffle(team1)
                random.shuffle(team2)
                if random.random() > 0.5:
                    best_combo = team1 + team2
                else:
                    best_combo = team2 + team1

    return best_combo

def get_next_players(exclude_players, count=4):
    candidates = [
        p for p, data in st.session_state.players.items() 
        if data['active'] and p not in exclude_players
    ]
    
    def is_compatible(group_names):
        if not st.session_state.get('enable_balancing', True):
            return True
        levels = {st.session_state.players[n].get('level', '有點累組') for n in group_names}
        if "死亡之組" in levels and "休閒組" in levels:
            return False
        return True

    ranked = sorted(candidates, key=lambda x: (st.session_state.players[x]['games'], random.random()))
    
    if len(ranked) < count:
        return None

    for i in range(len(ranked)):
        seed = ranked[i]
        valid_group = [seed]
        
        for other in ranked:
            if other == seed: continue
            
            temp_group = valid_group + [other]
            if is_compatible(temp_group):
                valid_group.append(other)
            
            if len(valid_group) == count:
                return balance_teams(valid_group)
    
    return None

def finish_and_next(court_id):
    current_players = st.session_state.courts[court_id]
    if current_players:
        record = f"場地 {court_id}: {current_players[0]}+{current_players[1]} vs {current_players[2]}+{current_players[3]}"
        st.session_state.history.insert(0, record)
        
        for p in current_players:
            if p in st.session_state.players:
                st.session_state.players[p]['games'] += 1
    
    st.session_state.courts[court_id] = []
    
    busy_players = []
    for c_id, p_list in st.session_state.courts.items():
        if c_id != court_id and p_list:
            busy_players.extend(p_list)
            
    next_group = get_next_players(exclude_players=busy_players, count=4)
    
    if next_group:
        st.session_state.courts[court_id] = next_group
        st.session_state.court_status[court_id] = "EDITING"
        st.toast(f"場地 {court_id} 更新完畢！", icon="✅")
        save_state()
    else:
        st.warning("休息區人數不足 4 人，無法自動排下一場，請等待其他場地結束。")

def reset_court(court_id):
    st.session_state.courts[court_id] = []
    st.session_state.court_status[court_id] = "EDITING"
    save_state()

def remove_player_from_court(court_id, player_name):
    if player_name in st.session_state.courts[court_id]:
        st.session_state.courts[court_id].remove(player_name)
        save_state()

def start_game(court_id):
    players = st.session_state.courts[court_id]
    if len(players) == 4:
        balanced = balance_teams(players)
        st.session_state.courts[court_id] = balanced
        st.session_state.court_status[court_id] = "PLAYING"
        save_state()
        st.toast(f"場地 {court_id} 比賽開始！(已平衡戰力)")
    else:
        st.warning("人數不足 4 人，無法開始")

def manual_add_player(name):
    target_court = None
    active_courts = sorted(st.session_state.courts.keys())
    for cid in active_courts: 
        if len(st.session_state.courts[cid]) < 4:
            target_court = cid
            break
            
    if target_court:
        st.session_state.courts[target_court].append(name)
        st.toast(f"已將 {name} 加入場地 {target_court}")
        save_state()
        return True
    else:
        st.warning("所有場地已滿！")
        return False

# --- UI 介面 ---

st.title("🏸 分組真的好難所以我做了一個自動輪替看板")

# --- 頁面導航 ---
page = st.sidebar.radio("📍 選單", ["🏸 排程看板", "📘 使用說明 & 演算法"], index=0)

if page == "📘 使用說明 & 演算法":
    st.header("📘 系統使用說明")
    st.markdown("""
    ### 如何設定 OpenAI API Key
    1. 進入 Streamlit Community Cloud 的 App Dashboard。
    2. 點擊 App 旁邊的 "..." > "Settings"。
    3. 選擇 "Secrets" 標籤。
    4. 貼上以下內容（將 `sk-...` 換成你的 Key）：
    ```toml
    OPENAI_API_KEY = "sk-proj-xxxxxxxxxxxxxx"
    ```
    """)
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            readme_content = f.read()
        st.markdown(readme_content)
    except FileNotFoundError:
        pass
    st.stop() 

# 側邊欄：設定
with st.sidebar:
    st.header("⚙️ 設定 & 人員管理")
    
    # 檢查 API Key 狀態
    if api_key:
        st.success("API Key 已設定 (OpenAI)")
    else:
        st.error("未偵測到 API Key")

    current_court_num = len(st.session_state.courts)
    selected_court_num = st.radio("場地數量", [1, 2], index=1 if current_court_num >= 2 else 0, horizontal=True)
    
    st.session_state.enable_balancing = st.toggle("啟用戰力平衡 (分組優化)", value=st.session_state.get('enable_balancing', True))
    
    if selected_court_num != current_court_num:
        if selected_court_num > current_court_num:
            for i in range(current_court_num + 1, selected_court_num + 1):
                st.session_state.courts[i] = []
                st.session_state.court_status[i] = "EDITING"
        else:
            for i in range(current_court_num, selected_court_num, -1):
                if i in st.session_state.courts:
                    del st.session_state.courts[i]
                    if i in st.session_state.court_status:
                        del st.session_state.court_status[i]
        save_state()
        st.rerun()
    
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
            selected = random.sample(pokemon_roster, 12)
            for name, level in selected: 
                add_player(name, level)
            st.rerun()

    st.divider()
    
    # --- OpenAI 截圖匯入 ---
    st.subheader("📸 匯入 Line 投票截圖")
    st.caption("使用 OpenAI AI 視覺辨識 (需設定 Secrets)")
    
    uploaded_file = st.file_uploader("上傳截圖", type=["jpg", "png", "jpeg"])
    
    if uploaded_file is not None:
        if st.button("🤖 AI 開始辨識"):
            with st.spinner("AI 正在看圖說故事..."):
                names = process_image_with_openai(uploaded_file)
            
            if names:
                st.session_state.ocr_results = names
                st.success(f"辨識成功！找到 {len(names)} 個名字")
            else:
                st.warning("未能辨識出名單，請確認圖片清晰度或 Key 是否正確。")

    # 顯示辨識結果供確認
    if st.session_state.ocr_results:
        st.caption("請勾選要加入的人員：")
        
        with st.form("ocr_confirm_form"):
            selected_ocr_names = []
            cols = st.columns(2)
            for i, name in enumerate(st.session_state.ocr_results):
                is_exist = name in st.session_state.players
                label = f"{name} (已存在)" if is_exist else name
                checked = st.checkbox(label, value=(not is_exist), key=f"ocr_{i}", disabled=is_exist)
                if checked and not is_exist:
                    selected_ocr_names.append(name)
            
            ocr_level = st.selectbox("批次設定分組", ["死亡之組", "有點累組", "休閒組"], index=1)
            
            if st.form_submit_button("確認加入選取人員"):
                count = 0
                for n in selected_ocr_names:
                    if add_player(n, ocr_level):
                        count += 1
                st.toast(f"成功加入 {count} 人！")
                st.session_state.ocr_results = [] 
                st.rerun()
        
        if st.button("放棄/清除結果"):
             st.session_state.ocr_results = []
             st.rerun()

    st.divider()

    st.write("勾選 = 可上場 / 取消 = 暫離")
    
    sorted_players = sorted(st.session_state.players.items(), key=lambda x: -x[1]['games'])
    
    for name, data in sorted_players:
        c1, c2, c3 = st.columns([5, 1, 1])
        with c1:
            lv_icon = {"死亡之組": "💀", "有點累組": "😓", "休閒組": "☕"}.get(data.get('level'), "😓")
            
            # 使用 popover 製作編輯選單
            with st.popover(f"**{name}** {lv_icon} ({data['games']}場)"):
                st.markdown(f"#### 編輯 {name}")
                new_n = st.text_input("姓名", value=name, key=f"edit_name_{name}")
                new_l = st.selectbox("分組", ["死亡之組", "有點累組", "休閒組"], 
                                     index=["死亡之組", "有點累組", "休閒組"].index(data.get('level', "有點累組")),
                                     key=f"edit_lv_{name}")
                new_g = st.number_input("場次數修正", min_value=0, value=data['games'], key=f"edit_gm_{name}")
                
                if st.button("儲存修改", key=f"save_{name}"):
                    if edit_player(name, new_n, new_l, new_g):
                        st.toast(f"已更新 {new_n}")
                        st.rerun()

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

active_courts = sorted(st.session_state.courts.keys())
court_cols = st.columns(len(active_courts)) 

for i, court_id in enumerate(active_courts): 
    with court_cols[i]:
        container = st.container(border=True)
        container.markdown(f"### 🏸 場地 {court_id}")
        
        current_p = st.session_state.courts[court_id]
        c_status = st.session_state.court_status.get(court_id, "EDITING")

        def fmt_p(name):
            if name == "waiting...": return name
            p_data = st.session_state.players.get(name)
            if not p_data: return name
            lv = p_data.get('level', '')
            icon = {"死亡之組": "💀", "有點累組": "😓", "休閒組": "☕"}.get(lv, "")
            return f"{name} {icon}"

        if current_p:
            if c_status == "PLAYING":
                display_p = current_p + ["waiting..."] * (4 - len(current_p))
                d_p = [fmt_p(x) for x in display_p]

                c_team1, c_vs, c_team2 = container.columns([2,1,2])
                with c_team1:
                    st.info(f"{d_p[0]}\n\n{d_p[1]}")
                with c_vs:
                    st.markdown("<br><div style='text-align: center'>VS</div>", unsafe_allow_html=True)
                with c_team2:
                    st.error(f"{d_p[2]}\n\n{d_p[3]}")
                
                if container.button(f"⏱️ 結束 & 換下一組", key=f"next_{court_id}", type="primary", use_container_width=True):
                    finish_and_next(court_id)
                    st.rerun()
                    
            else:
                st.caption("調整中 (點擊 ❌ 可移除)")
                for p in current_p:
                    ec1, ec2 = container.columns([4, 1])
                    ec1.write(f"👤 {fmt_p(p)}")
                    if ec2.button("❌", key=f"rm_{court_id}_{p}"):
                        remove_player_from_court(court_id, p)
                        st.rerun()
                
                if len(current_p) < 4:
                    container.info(f"等待加入... ({len(current_p)}/4)")
                else:
                    if container.button("🚀 開始對戰 (鎖定)", key=f"start_game_{court_id}", type="primary", use_container_width=True):
                        start_game(court_id)
                        st.rerun()

            if container.button("清除", key=f"cls_{court_id}"):
                reset_court(court_id)
                st.rerun()
        else:
            container.write("❌ 目前空場")
            busy = []
            for c, p in st.session_state.courts.items():
                if p: busy.extend(p)
            
            preview = get_next_players(busy, 4)
            if preview:
                container.caption(f"預計下組: {','.join(preview)}")
                if container.button("🚀 開始安排", key=f"start_{court_id}", type="primary", use_container_width=True):
                    finish_and_next(court_id)
                    st.rerun()
            else:
                container.warning("休息區人數不足")

st.divider()
c_rest, c_hist = st.columns([1, 1])

with c_rest:
    st.subheader("💤 休息中 / 等候區")
    on_court = []
    for p_list in st.session_state.courts.values():
        on_court.extend(p_list)
    
    waiting = [p for p, d in st.session_state.players.items() if d['active'] and p not in on_court]
    waiting_sorted = sorted(waiting, key=lambda x: (st.session_state.players[x]['games'], random.random()))
    
    if waiting_sorted:
        st.write(f"目前 {len(waiting_sorted)} 人候位：")
        for p in waiting_sorted:
            d = st.session_state.players[p]
            lv = d.get('level', '有點累組')
            icon = {"死亡之組": "💀", "有點累組": "😓", "休閒組": "☕"}.get(lv, "😓")
            
            if st.button(f"➕ {p} {icon} ({d['games']}場)", key=f"btn_add_{p}"):
                 manual_add_player(p)
                 st.rerun()
    else:
        st.write("無人休息")

with c_hist:
    st.subheader("📜 對戰紀錄")
    for rec in st.session_state.history[:10]: 
        st.text(rec)