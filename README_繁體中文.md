# 歐盟鋼鐵配額追蹤系統

自動擷取歐盟 TARIC 資料庫的鋼鐵關稅配額資料。

---

## 什麼是關稅配額？

**關稅配額 (Tariff Quota)** 是歐盟對進口鋼鐵的貿易保護措施：

| 情況 | 關稅 |
|------|------|
| 配額內進口 | 正常關稅（通常較低） |
| **配額耗盡後進口** | **額外 25% 關稅** |

### 配額週期

| 季度 | 期間 | 起始日 |
|------|------|--------|
| Q1 | 1月 - 3月 | 1月1日 |
| Q2 | 4月 - 6月 | 4月1日 |
| Q3 | 7月 - 9月 | 7月1日 |
| Q4 | 10月 - 12月 | 10月1日 |

### 為何需要追蹤？

- **提前規劃進口時機** - 在配額耗盡前完成進口
- **成本預估** - 計算是否值得進口
- **客戶服務** - 即時通知客戶配額狀態

---

## 快速開始

```powershell
# 使用 numberscrapping 專案的虛擬環境執行
& "c:/Users/lyen/Downloads/numberscrapping project/.venv/Scripts/python.exe" "c:/Users/lyen/Downloads/EU Quota/main.py"
```

### 執行模式

| 指令 | 說明 |
|------|------|
| `python main.py` | 互動模式（會詢問確認） |
| `python main.py --auto` | 自動模式（適合排程） |

---

## 輸出檔案

檔案儲存於 `data/output/`（自動建立）：

| 檔案 | 說明 |
|------|------|
| `eu_quota_report_YYYYMMDD.xlsx` | 完整資料 |
| `eu_quota_report_YYYYMMDD_customer.xlsx` | 客戶報告 |

### 客戶報告欄位

| 欄位 | 說明 |
|------|------|
| Product Category | 產品類別 |
| Origin | 原產地 |
| Order Number | 配額編號（6位數） |
| Initial Quota (kg) | 初始配額量 |
| Quota Used (kg) | 已使用量 |
| Used (%) | 已使用百分比 |
| Remaining (kg) | 剩餘配額 |
| Critical | 是否緊急 |
| Days Left in Quarter | 本季剩餘天數 |
| Est. Days to Exhaustion | 預估耗盡天數 |

---

## 專案結構

```
EU Quota/
├── eu_quota_scraper/       # 核心套件
│   ├── config.py           # 設定、URL 建構
│   ├── scraper.py          # Selenium 爬蟲
│   ├── data_processor.py   # 資料處理計算
│   └── exporter.py         # Excel 輸出
├── main.py                 # 主程式入口
├── requirements.txt        # 依賴套件
└── EU Quota URL's.xlsx     # 輸入：配額清單
```

---

## 技術說明

- **配額編號格式**：自動補零至 6 位數（如 `98967` → `098967`）
- **執行時間**：全部 189 筆約需 15-20 分鐘
- **請求間隔**：每筆間隔 1 秒，避免對伺服器造成負擔

---

## 設定每日自動執行

### Windows 工作排程器

1. 開啟「工作排程器」→ 建立基本工作
2. 名稱：「EU Quota 配額更新」
3. 觸發程序：每天，選擇時間
4. 動作：啟動程式
   - 程式：`c:\Users\lyen\Downloads\numberscrapping project\.venv\Scripts\python.exe`
   - 引數：`c:\Users\lyen\Downloads\EU Quota\main.py --auto`

---

## 資料來源

[歐盟 TARIC 配額資料庫](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
