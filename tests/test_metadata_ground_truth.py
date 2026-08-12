"""End-to-end extraction against published papers with known ground truth.

SKIPPED unless the PDFs are present. They live in `local/testpapers/`, which
is gitignored -- shipping ~19 MB of other people's papers in the repo is not
something to do casually, and CI does not need them to catch a regression in
the rules, which `test_layout_metadata.py` covers with hand-built spans.

To run these:

    mkdir -p local/testpapers && cd local/testpapers
    while read -r name id; do curl -sL -o "$name.pdf" "https://arxiv.org/pdf/$id"
    done <<'IDS'
    attention 1706.03762
    bert      1810.04805
    resnet    1512.03385
    effnet    1905.11946
    cot       2201.11903
    clip      2103.00020
    gpt3      2005.14165
    ieee_a    2402.02414
    adam      1412.6980
    lora      2106.09685
    vit       2010.11929
    gan       1406.2661
    sam       2304.02643
    mamba     2312.00752
    ddpm      2006.11239
    whisper   2212.04356
    word2vec  1301.3781
    IDS

Chosen for variety in what has to be read, not in subject:

    small caps          adam, lora, vit -- capitals set larger than the rest
    hyphenated title    lora, wrapping as "LARGE LAN-" / "GUAGE MODELS"
    rotated stamp       attention, whose arXiv stamp outsizes its title
    ligature            effnet, "Efficient" as the single glyph U+FB01
    loose accent        sam ("Dollár"), gan ("Université")
    author layouts      columns, one comma-separated line, one name per row
    author counts       2 to 31
"""

from pathlib import Path

import pytest

from domain.ingestion.metadata_extractor import extract_metadata_layout
from domain.ingestion.pdf_parser import extract_layout, extract_text

PAPERS = Path(__file__).resolve().parents[1] / "local" / "testpapers"

GROUND_TRUTH = {
    "attention": (
        "Attention Is All You Need", "2017",
        ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit",
         "Llion Jones", "Aidan N. Gomez", "Łukasz Kaiser", "Illia Polosukhin"],
    ),
    "bert": (
        "BERT: Pre-training of Deep Bidirectional Transformers for "
        "Language Understanding", "2018",
        ["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"],
    ),
    "resnet": (
        "Deep Residual Learning for Image Recognition", "2015",
        ["Kaiming He", "Xiangyu Zhang", "Shaoqing Ren", "Jian Sun"],
    ),
    "effnet": (
        "EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks",
        "2019",
        ["Mingxing Tan", "Quoc V. Le"],
    ),
    "cot": (
        "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        "2022",
        ["Jason Wei", "Xuezhi Wang", "Dale Schuurmans", "Maarten Bosma",
         "Brian Ichter", "Fei Xia", "Ed H. Chi", "Quoc V. Le", "Denny Zhou"],
    ),
    "clip": (
        "Learning Transferable Visual Models From Natural Language Supervision",
        "2021",
        ["Alec Radford", "Jong Wook Kim", "Chris Hallacy", "Aditya Ramesh",
         "Gabriel Goh", "Sandhini Agarwal", "Girish Sastry", "Amanda Askell",
         "Pamela Mishkin", "Jack Clark", "Gretchen Krueger", "Ilya Sutskever"],
    ),
    "ieee_a": (
        "Navigate Biopsy with Ultrasound under Augmented Reality Device: "
        "Towards Higher System Performance", "2024",
        ["Haowei Li", "Wenqing Yan", "Jiasheng Zhao", "Yuqi Ji",
         "Long Qian", "Hui Ding", "Zhe Zhao", "Guangzhi Wang"],
    ),
    # Small caps: the capitals are set larger than the rest, so grouping rows
    # by bounding-box top rather than baseline gave "A : A M S O".
    "adam": (
        "ADAM: A METHOD FOR STOCHASTIC OPTIMIZATION", "2014",
        ["Diederik P. Kingma", "Jimmy Lei Ba"],
    ),
    # Small caps AND a title hyphenated across the line break.
    "lora": (
        "LORA: LOW-RANK ADAPTATION OF LARGE LANGUAGE MODELS", "2021",
        ["Edward Hu", "Yelong Shen", "Phillip Wallis", "Zeyuan Allen-Zhu",
         "Yuanzhi Li", "Shean Wang", "Lu Wang", "Weizhu Chen"],
    ),
    "vit": (
        "AN IMAGE IS WORTH 16X16 WORDS: TRANSFORMERS FOR IMAGE "
        "RECOGNITION AT SCALE", "2020",
        ["Alexey Dosovitskiy", "Lucas Beyer", "Alexander Kolesnikov",
         "Dirk Weissenborn", "Xiaohua Zhai", "Thomas Unterthiner",
         "Mostafa Dehghani", "Matthias Minderer", "Georg Heigold",
         "Sylvain Gelly", "Jakob Uszkoreit", "Neil Houlsby"],
    ),
    # An accented affiliation: "Université" did not match the folded list.
    "gan": (
        "Generative Adversarial Nets", "2014",
        ["Ian J. Goodfellow", "Jean Pouget-Abadie", "Mehdi Mirza", "Bing Xu",
         "David Warde-Farley", "Sherjil Ozair", "Aaron Courville",
         "Yoshua Bengio"],
    ),
    # A surname carrying a loose accent glyph: "Doll" + U+00B4 + "ar".
    "sam": (
        "Segment Anything", "2023",
        ["Alexander Kirillov", "Eric Mintun", "Nikhila Ravi", "Hanzi Mao",
         "Chloe Rolland", "Laura Gustafson", "Tete Xiao", "Spencer Whitehead",
         "Alexander C. Berg", "Wan-Yen Lo", "Piotr Dollár", "Ross Girshick"],
    ),
    "mamba": (
        "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        "2023", ["Albert Gu", "Tri Dao"],
    ),
    "ddpm": (
        "Denoising Diffusion Probabilistic Models", "2020",
        ["Jonathan Ho", "Ajay Jain", "Pieter Abbeel"],
    ),
    "whisper": (
        "Robust Speech Recognition via Large-Scale Weak Supervision", "2022",
        ["Alec Radford", "Jong Wook Kim", "Tao Xu", "Greg Brockman",
         "Christine McLeavey", "Ilya Sutskever"],
    ),
    "word2vec": (
        "Efficient Estimation of Word Representations in Vector Space", "2013",
        ["Tomas Mikolov", "Kai Chen", "Greg Corrado", "Jeffrey Dean"],
    ),
}


def _metadata(name):
    path = PAPERS / f"{name}.pdf"
    if not path.exists():
        pytest.skip(f"{path} not present -- see this module's docstring")
    layout = extract_layout(str(path))
    _, text = extract_text(str(path))
    return extract_metadata_layout(layout[0], text)


@pytest.mark.parametrize("name", sorted(GROUND_TRUTH))
def test_title(name):
    assert _metadata(name).title == GROUND_TRUTH[name][0]


@pytest.mark.parametrize("name", sorted(GROUND_TRUTH))
def test_year(name):
    """Every one of these was wrong or missing before.

    attention.pdf in particular returned 2014, taken from Google's licence
    boilerplate -- three years before the paper existed.
    """
    assert _metadata(name).year == GROUND_TRUTH[name][1]


@pytest.mark.parametrize("name", sorted(GROUND_TRUTH))
def test_authors_exactly(name):
    """Exact list, in order. Not "contains" -- the old extractor's failure was
    extra entries (employers, the paper's own title), which a containment
    assertion would have passed."""
    assert _metadata(name).authors == GROUND_TRUTH[name][2]


@pytest.mark.parametrize("name", sorted(GROUND_TRUTH))
def test_no_affiliation_survives_as_an_author(name):
    """The specific shipped symptom: `author = {Google Brain}`."""
    authors = " | ".join(_metadata(name).authors).lower()
    for word in ("google", "microsoft", "university", "research", "institute",
                 "openai", "tsinghua", "brain team"):
        assert word not in authors, f"{word!r} came back as an author"
