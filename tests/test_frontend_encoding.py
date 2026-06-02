from pathlib import Path


def test_static_frontend_thai_text_is_not_mojibake():
    html = Path("th_evi/static/index.html").read_text(encoding="utf-8")

    expected_thai_labels = [
        "\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c\u0e04\u0e27\u0e32\u0e21\u0e15\u0e49\u0e2d\u0e07\u0e01\u0e32\u0e23",
        "\u0e04\u0e48\u0e32\u0e2b\u0e25\u0e31\u0e01",
        "\u0e1e\u0e37\u0e49\u0e19\u0e17\u0e35\u0e48\u0e17\u0e35\u0e48\u0e08\u0e30\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c",
        "\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c\u0e41\u0e25\u0e30\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01",
    ]
    mojibake_fragments = [
        "\u0e40\u0e18",
        "\u0e40\u0e19\u20ac",
        "\u0e42\u20ac",
        "\u0e42\u2013",
    ]

    for label in expected_thai_labels:
        assert label in html
    for fragment in mojibake_fragments:
        assert fragment not in html
