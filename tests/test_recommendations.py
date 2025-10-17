from tgac.bot.handlers import build_recommendations_text
from tgac.bot.recommendations import AppRecommendation, filter_official_recommendations


def test_filter_official_recommendations_keeps_official_links():
    recommendations = [
        AppRecommendation(
            name="Official VPN",
            platform="Android",
            url="https://play.google.com/store/apps/details?id=com.example.vpn",
        ),
        AppRecommendation(
            name="Unofficial APK",
            platform="android",
            url="https://downloads.example.com/vpn.apk",
        ),
    ]

    result = filter_official_recommendations(recommendations)

    assert [item.name for item in result.allowed] == ["Official VPN"]
    assert [item.name for item in result.rejected] == ["Unofficial APK"]


def test_filter_allows_linux_links_without_store_constraint():
    recommendations = [
        AppRecommendation(
            name="Linux Client",
            platform="linux",
            url="https://example.org/releases/linux-client.tar.gz",
        )
    ]

    result = filter_official_recommendations(recommendations)

    assert [item.name for item in result.allowed] == ["Linux Client"]
    assert not result.rejected


def test_build_recommendations_text_filters_out_non_official_links():
    recommendations = [
        AppRecommendation(
            name="Official VPN",
            platform="android",
            url="https://play.google.com/store/apps/details?id=com.example.vpn",
        ),
        AppRecommendation(
            name="Side-loaded VPN",
            platform="android",
            url="https://downloads.example.com/vpn.apk",
        ),
    ]

    text = build_recommendations_text(recommendations)

    assert "Official VPN" in text
    assert "Side-loaded VPN" not in text
    assert "⚠️" in text


def test_build_recommendations_text_reports_empty_official_list():
    recommendations = [
        AppRecommendation(
            name="Unsupported Platform",
            platform="amiga",
            url="https://example.com/app",
        )
    ]

    text = build_recommendations_text(recommendations)

    assert "Нет приложений из официальных магазинов" in text
    assert "⚠️" in text
