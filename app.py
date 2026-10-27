import asyncio

import pandas as pd
import streamlit as st

from fiyat_takip.config import Settings
from fiyat_takip.miniode import CatalogError, get_catalog, get_collections
from fiyat_takip.preferences import load_minimum_price, save_minimum_price
from fiyat_takip.reports import create_excel, results_frame, save_excel
from fiyat_takip.service import run_scan
from fiyat_takip.storage import load_history, save_results
from fiyat_takip.telegram import send_report


st.set_page_config(
    page_title="Onur Fiyat Takip",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = Settings.load()
database_path = settings.data_dir / "price_history.db"
preferences_path = settings.data_dir / "preferences.json"

for key, default in {
    "results": None,
    "report_bytes": None,
    "report_name": "fiyat_raporu.xlsx",
    "minimum_price_filter": load_minimum_price(preferences_path),
}.items():
    st.session_state.setdefault(key, default)


@st.cache_data(ttl=600, max_entries=4, show_spinner=False)
def load_collections() -> list[dict[str, str]]:
    return get_collections(settings.request_timeout)


st.title(":material/monitoring: Onur fiyat takip")
st.caption(
    "Miniöde ürünlerini Akakçe ve Cimri fiyatlarıyla karşılaştırır, "
    "sonuçları geçmişe kaydeder ve raporlar."
)

with st.sidebar:
    st.header(":material/tune: Tarama ayarları")
    try:
        collections = load_collections()
    except CatalogError as exc:
        collections = []
        st.error(str(exc))

    category_options = {"Tüm katalog": None}
    category_options.update(
        {item["title"]: item["handle"] for item in collections if item["title"]}
    )
    with st.form("scan_settings"):
        selected_category = st.selectbox("Kategori", list(category_options))
        selected_handle = category_options[selected_category]
        minimum_price = st.number_input(
            "En düşük Miniöde fiyatı",
            min_value=0,
            step=50,
            format="%d",
            key="minimum_price_filter",
            persist_state="session",
            help="İlk değer 5.000 ₺'dir. Taramada kullandığınız son değer kaydedilir.",
        )
        only_available = st.checkbox("Yalnızca stoktaki ürünler", value=True)
        maximum_products = st.number_input(
            "En fazla taranacak ürün (0 = tümü)",
            min_value=0,
            max_value=2_000,
            value=25,
            step=5,
        )
        notify_telegram = st.checkbox(
            "Telegram bildirimi gönder",
            value=settings.telegram_enabled,
            disabled=not settings.telegram_enabled,
            help=(
                "Telegram ayarları hazır."
                if settings.telegram_enabled
                else "Önce .streamlit/secrets.toml dosyasını doldurun."
            ),
        )
        start_scan = st.form_submit_button(
            "Taramayı başlat",
            type="primary",
            icon=":material/search:",
            width="stretch",
        )
    st.caption(
        "Chrome yardımcısı açıksa taramada otomatik kullanılır; "
        "yanıt vermezse yerleşik tarayıcıya geçilir."
    )

if start_scan:
    save_minimum_price(preferences_path, int(minimum_price))
    with st.status("Miniöde kataloğu okunuyor…", expanded=True) as status:
        try:
            catalog_limit = (
                max(int(maximum_products) * 10, 250) if maximum_products else None
            )
            products = get_catalog(
                selected_handle,
                settings.request_timeout,
                max_products=catalog_limit,
            )
        except CatalogError as exc:
            status.update(label="Katalog okunamadı", state="error")
            st.error(str(exc))
            st.stop()

        raw_count = len(products)
        if only_available:
            products = [product for product in products if product.available]
        products = [product for product in products if product.price >= minimum_price]
        if maximum_products:
            products = products[: int(maximum_products)]

        if not products:
            status.update(label="Filtrelere uyan ürün bulunamadı", state="error")
            st.warning("Kategori, stok veya fiyat filtresini değiştirip yeniden deneyin.")
            st.stop()

        st.markdown(f"{raw_count} katalog kaydından **{len(products)}** ürün taranacak.")
        status.update(label="Katalog hazır", state="complete", expanded=False)

    progress = st.progress(0)
    progress_text = st.empty()

    def update_progress(current: int, total: int) -> None:
        progress.progress(current / total)
        progress_text.write(f"Piyasa kaynakları taranıyor: {current}/{total}")

    try:
        with st.spinner("Piyasa fiyatları karşılaştırılıyor…"):
            results = asyncio.run(run_scan(products, settings, update_progress))
    except Exception as exc:
        st.error(f"Tarama tamamlanamadı: {exc}")
        st.stop()

    report_bytes = create_excel(results)
    report_path = save_excel(settings.report_dir, report_bytes)
    save_results(database_path, results)
    st.session_state.results = results
    st.session_state.report_bytes = report_bytes
    st.session_state.report_name = report_path.name

    if notify_telegram:
        sent, message = send_report(results, report_bytes, settings)
        (st.success if sent else st.warning)(message)
    st.success(f"Tarama tamamlandı: {len(results)} ürün incelendi.")

results = st.session_state.results
if results:
    frame = results_frame(results)
    total = len(frame)
    critical = frame["Durum"].str.contains("Kritik|Yüksek|Pahalı", na=False).sum()
    competitive = frame["Durum"].str.contains("Rekabetçi|Dengeli", na=False).sum()
    missing = frame["Durum"].str.contains("Bulunamadı|Engellendi", na=False).sum()

    st.divider()
    with st.container(horizontal=True):
        st.metric("Toplam ürün", total, border=True)
        st.metric("Müdahale gereken", int(critical), border=True)
        st.metric("Rekabetçi", int(competitive), border=True)
        st.metric("Piyasa alınamadı", int(missing), border=True)

    st.download_button(
        "Excel raporunu indir",
        data=st.session_state.report_bytes,
        file_name=st.session_state.report_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        icon=":material/download:",
    )

    filter_name = st.segmented_control(
        "Sonuç filtresi",
        ["Tümü", "Müdahale gereken", "Rekabetçi", "Piyasa alınamayan"],
        default="Tümü",
        required=True,
        key="result_filter",
    )
    filtered = frame
    if filter_name == "Müdahale gereken":
        filtered = frame[frame["Durum"].str.contains("Kritik|Yüksek|Pahalı", na=False)]
    elif filter_name == "Rekabetçi":
        filtered = frame[frame["Durum"].str.contains("Rekabetçi|Dengeli", na=False)]
    elif filter_name == "Piyasa alınamayan":
        filtered = frame[
            frame["Durum"].str.contains("Bulunamadı|Engellendi", na=False)
        ]

    display_columns = [
        "Ürün",
        "Kondisyon",
        "Miniöde Fiyatı",
        "Akakçe Fiyatı",
        "Cimri Fiyatı",
        "Akakçe Durumu",
        "Cimri Durumu",
        "Piyasa Referansı",
        "Eşleşen Ürün",
        "Piyasa URL",
        "Fark %",
        "Durum",
        "Öneri",
        "Akakçe Arama",
        "Cimri Arama",
        "SKU",
    ]
    st.dataframe(
        filtered.reindex(columns=display_columns),
        hide_index=True,
        key="results_table",
        column_config={
            "Miniöde Fiyatı": st.column_config.NumberColumn(format="%.2f TL"),
            "Akakçe Fiyatı": st.column_config.NumberColumn(format="%.2f TL"),
            "Cimri Fiyatı": st.column_config.NumberColumn(format="%.2f TL"),
            "Piyasa Referansı": st.column_config.NumberColumn(format="%.2f TL"),
            "Piyasa URL": st.column_config.LinkColumn(
                "Piyasa sayfası", display_text="Eşleşmeyi aç"
            ),
            "Fark %": st.column_config.NumberColumn(format="%.1f%%"),
            "Akakçe Arama": st.column_config.LinkColumn(
                "Akakçe", display_text="Manuel kontrol"
            ),
            "Cimri Arama": st.column_config.LinkColumn(
                "Cimri", display_text="Manuel kontrol"
            ),
        },
    )
else:
    st.info("Sol panelden ayarları seçip taramayı başlatın.")

st.divider()
with st.expander("Fiyat geçmişi", expanded=False):
    history = load_history(database_path)
    if history:
        st.dataframe(
            pd.DataFrame(history),
            hide_index=True,
            key="history_table",
            column_config={
                "Miniöde Fiyatı": st.column_config.NumberColumn(format="%.2f TL"),
                "Piyasa Referansı": st.column_config.NumberColumn(format="%.2f TL"),
            },
        )
    else:
        st.caption("Henüz kayıtlı tarama bulunmuyor.")
