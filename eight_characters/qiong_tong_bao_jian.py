"""Qiong Tong Bao Jian's climate table: the stems each Day Master's birth month calls
for, as the Climate school (调候 Tiao Hou) reads them (docs/Today.md, Climate).

The text is prose, not a table. The copy is Wikisource's 穷通宝鉴, revision 2294674
(14 June 2023): https://zh.wikisource.org/w/index.php?oldid=2294674. Each entry keeps
the stems in the text's order of use and the passage they are taken from, word for
word, with the heading it stands under; tests/fixtures holds the revision, and the
tests find every passage in it, line breaks aside. The reduction:

- What the text says to use for the month, unconditionally, in the order it ranks
  them: 先…后…, …为尊/为用/为主/为要…, …次之/佐之/为佐/为助/为辅. A season's
  passage counts for a month it names.
- What the text says of the month alone comes first. A statement it shares with
  other months (总之正二月甲木, a season's 三春…) counts for a month only where nothing
  is said of that month alone: 甲 Jia in 寅 Yin takes 丙癸 (Bing, Gui) from 正月甲木,
  and in 卯 Mao, whose own passage names no stem to use, 庚戊 (Geng, Wu) from
  总之正二月甲木. A sentence that only adds a stem for one month to a shared statement
  (九月土盛，宜甲木疏之; 惟初冬壬旺，取戊制之; 三月土重晦光，取甲佐之为妙) does not set it
  aside: its stem follows the shared ones.
- Where the month's use is stated more than once, a statement that ranks its stems
  over one that only lists them (专用 X Y, 并用, 兼用, 齐用), then the fullest, and
  of two as full, the later, which is usually the month's own summary. A statement
  that disclaims its order (非拘执先后) does not rank.
- A stem named only under a condition (或…, 若…, 如无…, 凡…者) or as a fallback is
  left out, and so is a role named without a stem (比劫, 财).
- Where the text divides a month at its middle term, the entry gives both halves.
"""

from dataclasses import dataclass
from typing import Final

from eight_characters.sexagenary import BRANCHES, STEMS


@dataclass(frozen=True)
class Later:
    """The stems for a month's second half, from its middle term, and their sentence."""

    stems: tuple[str, ...]
    sentence: str


@dataclass(frozen=True)
class ClimateEntry:
    day_master: str
    # The month branches the entry covers.
    months: str
    # The stems the text names as used, in its order.
    stems: tuple[str, ...]
    # The heading the sentence stands under, and the sentence, as the text has them.
    heading: str
    sentence: str
    # Where the text divides the month at its middle term: its second half.
    later: Later | None


TABLE: Final[tuple[ClimateEntry, ...]] = (
    ClimateEntry(
        day_master='甲',
        months='寅',
        stems=('丙', '癸'),
        heading='正月甲木',
        sentence='正月甲木，初春尚有余寒，得丙癸逢，富贵双全。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='卯',
        stems=('庚', '戊'),
        heading='正二月甲木',
        sentence='总之正二月甲木，有庚戊者上命。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='辰',
        stems=('庚', '壬'),
        heading='三月甲木',
        sentence='三月甲木，木气相竭。先取庚金，次用壬水。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='巳',
        stems=('癸', '丁'),
        heading='四月甲木',
        sentence='四月甲木退气，丙火司权，先癸后丁。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='午',
        stems=('癸', '丁', '庚'),
        heading='五六月甲木',
        sentence='五月先癸后丁庚金次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='未',
        stems=('丁', '庚'),
        heading='五六月甲木',
        sentence='六月三伏生寒，丁火退气。先丁后庚，无癸亦可。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='申',
        stems=('丁', '庚'),
        heading='七月甲木',
        sentence='七月甲木，丁火为尊，庚金次之，庚金不可少。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='酉',
        stems=('丁', '丙', '庚'),
        heading='八月甲木',
        sentence='八月甲木，木囚金旺。丁火为先，次用丙火，庚金再次。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='戌',
        stems=('丁', '壬', '癸'),
        heading='九月甲木',
        sentence='九月甲木，木星凋零，独爱丁火，壬癸滋扶',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='亥',
        stems=('庚', '丁', '丙'),
        heading='十月甲木',
        sentence='十月甲木，庚丁为要，丙火次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='子',
        stems=('丁', '庚', '丙'),
        heading='十一月甲木',
        sentence='十一月甲木，木性生寒，丁先庚后，丙火佐之。',
        later=None,
    ),
    ClimateEntry(
        day_master='甲',
        months='丑',
        stems=('庚', '丁'),
        heading='十二月甲木',
        sentence='先用庚噼甲，方引丁火始得木火有通明之象，故丁次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='寅',
        stems=('丙', '癸'),
        heading='正月乙木',
        sentence='故以丙火为先，癸水次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='卯',
        stems=('丙', '癸'),
        heading='二月乙木',
        sentence='二月乙木，阳气渐升，木不寒矣，以丙为君，癸为臣',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='辰',
        stems=('癸', '丙'),
        heading='三月乙木',
        sentence='三月乙木，阳气愈炽，先癸后丙。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='巳',
        stems=('癸', '丙', '庚', '辛'),
        heading='四月乙木',
        sentence='四月乙木专用癸水，丙火酌用，虽以庚辛佐癸，须辛透为清。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='午',
        stems=('癸',),
        heading='五月乙木',
        sentence='上半月属阳，仍用癸水。',
        later=Later(
            stems=('癸', '丙'),
            sentence='下半月属阴，三伏生寒，丙癸齐用。柱多金水，丙火为先，余皆用癸水为先。',
        ),
    ),
    ClimateEntry(
        day_master='乙',
        months='未',
        stems=('丙', '癸'),
        heading='三夏乙木',
        sentence='五六月先丙后癸，夏至前仍用癸水。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='申',
        stems=('丙', '癸'),
        heading='三秋乙木',
        sentence='三秋乙木，金神司令，先丙后癸，惟九月耑用癸水',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='酉',
        stems=('癸',),
        heading='八月乙木',
        sentence='在白露之后，桂蕊未开，耑用癸水以滋桂萼。',
        later=Later(
            stems=('丙', '癸'),
            sentence='若秋分后，桂花已开，却喜向阳，又宜用丙，癸水次之',
        ),
    ),
    ClimateEntry(
        day_master='乙',
        months='戌',
        stems=('癸', '辛'),
        heading='九月乙木',
        sentence='若见癸水，又遇辛金发水之源，定主科甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='亥',
        stems=('丙', '戊'),
        heading='十月乙木',
        sentence='十月乙木，木不受气，而壬水司令，取丙为用，戊土次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='子',
        stems=('丙',),
        heading='十一月乙木',
        sentence='不宜用癸以冻花木，故耑用丙火。',
        later=None,
    ),
    ClimateEntry(
        day_master='乙',
        months='丑',
        stems=('丙',),
        heading='三冬乙木',
        sentence='冬月之木，虽取戊制水，不可作用，耑取丙火则可。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='寅',
        stems=('壬', '庚', '辛'),
        heading='三春丙火',
        sentence='正月用壬，庚辛为助。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='卯',
        stems=('壬',),
        heading='二月丙火',
        sentence='二月丙火，阳气舒升，耑用壬水。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='辰',
        stems=('壬', '甲'),
        heading='三春丙火',
        sentence='耑用壬水为扶阳，名曰天和地润，既济功成。正月用壬，庚辛为助。二月耑用壬水。三月土重晦光，取甲佐之为妙。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='巳',
        stems=('壬',),
        heading='四月丙火',
        sentence='宜专用壬水，解炎威之力，成既济之功。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='午',
        stems=('壬',),
        heading='五月丙火',
        sentence='五月丙火，得壬高透，方为上命。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='未',
        stems=('壬', '庚'),
        heading='六月丙火',
        sentence='六月丙火退气，三伏生寒，壬水为用，取庚辅佐。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='申',
        stems=('壬',),
        heading='七月丙火',
        sentence='故仍用壬水，辅映光辉。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='酉',
        stems=('壬',),
        heading='八月丙火',
        sentence='仍用壬水辅映。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='戌',
        stems=('甲', '壬'),
        heading='九月丙火',
        sentence='必须先用甲木，次取壬水。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='亥',
        stems=('甲', '戊', '庚'),
        heading='十月丙火',
        sentence='十月丙火，太阳失令，得见甲戊庚出干，可云科甲',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='子',
        stems=('壬', '戊'),
        heading='十一月丙火',
        sentence='十一月丙火，冬至一阳生，弱中复强，壬水为最，戊土佐之。',
        later=None,
    ),
    ClimateEntry(
        day_master='丙',
        months='丑',
        stems=('壬', '甲'),
        heading='十二月丙火',
        sentence='喜壬为用。己土司令，土多又不可少甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='寅',
        stems=('庚', '甲'),
        heading='正月丁火',
        sentence='非庚不能噼甲，何以引丁，姑用庚金。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='卯',
        stems=('庚', '甲'),
        heading='二月丁火',
        sentence='二月丁火，溼乙伤丁，先庚后甲',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='辰',
        stems=('甲', '庚'),
        heading='三月丁火',
        sentence='先用甲木引丁制土，次看庚金。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='巳',
        stems=('甲', '庚'),
        heading='四月丁火',
        sentence='四月丁火乘旺，虽取甲引丁，必用庚噼甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='午',
        stems=('壬',),
        heading='五月丁火',
        sentence='用壬者，金妻水子。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='未',
        stems=('甲', '壬'),
        heading='六月之丁',
        sentence='专取甲木，壬水次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='申',
        stems=('甲', '庚'),
        heading='七月丁火',
        sentence='七月丁火，退气柔弱，端用甲木，金虽乘旺司权，无伤丁之理，仍取庚劈甲',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='酉',
        stems=('甲', '丙', '庚'),
        heading='三秋丁火',
        sentence='八月甲丙庚皆用',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='戌',
        stems=('甲', '庚'),
        heading='三秋丁火',
        sentence='九月耑用甲庚。',
        later=None,
    ),
    ClimateEntry(
        day_master='丁',
        months='亥子丑',
        stems=('甲', '庚', '癸', '戊'),
        heading='三冬丁火',
        sentence='三冬丁火，甲木为尊，庚金佐之，癸戊权宜酌用可也。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='寅卯',
        stems=('丙', '甲', '癸'),
        heading='三春戊土',
        sentence='正二月先丙后甲，癸又次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='辰',
        stems=('甲', '丙', '癸'),
        heading='三春戊土',
        sentence='三月先甲后丙，癸又次之，因戊土司权故也。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='巳',
        stems=('甲', '丙', '癸'),
        heading='四月戊土',
        sentence='故先用甲疏噼，次取丙癸为佐。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='午',
        stems=('壬', '甲', '丙'),
        heading='五月戊土',
        sentence='五月戊土，仲夏火炎，先看壬水，次取甲木，丙火酌用，用癸力微。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='未',
        stems=('癸', '丙', '甲'),
        heading='六月戊土',
        sentence='六月戊土，遇夏干枯，先看癸水，次用丙火甲木。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='申',
        stems=('丙', '癸', '甲'),
        heading='三秋戊土',
        sentence='七月戊土，阳气渐入，寒气渐出，先丙后癸，甲木次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='酉',
        stems=('丙', '癸'),
        heading='八月戊土',
        sentence='先丙后癸，不必木疏。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='戌',
        stems=('甲', '癸'),
        heading='九月戊土',
        sentence='九月戊土当权，不可专用丙，先看甲木，次取癸水，却忌化合。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='亥',
        stems=('甲', '丙'),
        heading='十月戊土',
        sentence='十月戊土，时值小阳，阳气略出，先用甲木，次取丙火。',
        later=None,
    ),
    ClimateEntry(
        day_master='戊',
        months='子丑',
        stems=('丙', '甲'),
        heading='十一二月',
        sentence='十一二月严寒冰冻，丙火为专，甲木为佐。',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='寅',
        stems=('丙',),
        heading='正月己土',
        sentence='盖因腊气未除，余寒未退，故丙为尊。',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='卯',
        stems=('甲', '癸'),
        heading='二月己土',
        sentence='先取甲木疏之，忌合。次取癸水润之。',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='辰',
        stems=('丙', '癸', '甲'),
        heading='三月己土',
        sentence='三月己土，正栽培禾稼之时，先丙后癸，土暖而润，随用甲疏',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='巳午未',
        stems=('癸', '丙'),
        heading='三夏己土',
        sentence='取癸为要，次用丙火。',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='申酉',
        stems=('癸', '丙', '辛'),
        heading='三秋己土',
        sentence='总之，三秋己土，先癸后丙，取辛辅癸。',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='戌',
        stems=('癸', '丙', '辛', '甲'),
        heading='三秋己土',
        sentence='总之，三秋己土，先癸后丙，取辛辅癸。九月土盛，宜甲木疏之',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='亥',
        stems=('丙', '甲', '戊'),
        heading='三冬己土',
        sentence='非丙暖不生，取丙为尊，甲木参酌。戊土癸水不用。惟初冬壬旺，取戊制之。',
        later=None,
    ),
    ClimateEntry(
        day_master='己',
        months='子丑',
        stems=('丙', '甲'),
        heading='三冬己土',
        sentence='非丙暖不生，取丙为尊，甲木参酌。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='寅',
        stems=('丙', '甲', '丁'),
        heading='正月庚金',
        sentence='总之，正月庚金，丙甲为上，丁火次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='卯',
        stems=('丁', '甲', '庚'),
        heading='二月庚金',
        sentence='故二月庚金，专用丁火，借甲引丁，借庚噼甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='辰',
        stems=('甲', '丁'),
        heading='三月庚金',
        sentence='故先甲后丁，不用庚噼甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='巳',
        stems=('壬', '戊', '丙'),
        heading='四月庚金',
        sentence='但先壬水，方得中和，故曰群金生夏，喜用勾陈。次取戊土，丙火佐之。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='午',
        stems=('壬', '癸'),
        heading='五月庚金',
        sentence='五月庚金，丁火旺烈，庚金败地，专用壬水，癸又次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='未',
        stems=('丁', '甲'),
        heading='六月庚金',
        sentence='六月庚金，三伏生寒，顽钝极矣，先用丁火，次取甲木。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='申',
        stems=('丁', '甲'),
        heading='七月庚金',
        sentence='专用丁火煅炼，次取甲木引丁',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='酉',
        stems=('丁', '甲', '丙'),
        heading='八月庚金',
        sentence='八月庚金，刚锐未退，用丁用甲，丙不可少。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='戌',
        stems=('甲', '壬'),
        heading='九月庚金',
        sentence='宜先用甲疏，后用壬洗，则金自出矣。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='亥',
        stems=('丁', '丙'),
        heading='十月庚金',
        sentence='十月庚金，水冷性寒，非丁莫造，非丙不暖。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='子',
        stems=('丁', '甲', '丙'),
        heading='十一月庚金',
        sentence='十一月庚金，天气严寒，仍取丁甲，次取丙火照暖。',
        later=None,
    ),
    ClimateEntry(
        day_master='庚',
        months='丑',
        stems=('丙', '丁', '甲'),
        heading='十二月庚金',
        sentence='先取丙火解冻，次取丁火炼金，甲亦不可少。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='寅',
        stems=('己', '壬', '庚'),
        heading='正月辛金',
        sentence='故正月辛金，先己后壬。己为君，庚为佐。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='卯',
        stems=('壬', '甲'),
        heading='二月辛金',
        sentence='二月辛金，阳和之际，壬水为尊，见戊己为病。得甲制伏',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='辰',
        stems=('壬', '甲'),
        heading='三月辛金',
        sentence='三月辛金，戊土司令，辛承正气，母旺子相，先壬后甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='巳',
        stems=('壬',),
        heading='四月辛金',
        sentence='四月辛金，时逢首夏，忌丙火之燥烈，喜壬水之洗淘。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='午',
        stems=('壬', '己'),
        heading='五月辛金',
        sentence='故壬己并用。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='未',
        stems=('壬', '庚'),
        heading='六月辛金',
        sentence='先用壬水，取庚佐之。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='申',
        stems=('壬', '甲', '戊'),
        heading='七月辛金',
        sentence='壬水为尊，甲戊酌用可也，癸水不可为用。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='酉',
        stems=('壬',),
        heading='八月辛金',
        sentence='八月辛金，当权得令，旺之极矣，专用壬水淘洗',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='戌',
        stems=('壬', '甲'),
        heading='九月辛金',
        sentence='须甲疏土，壬洩旺金，先壬后甲。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='亥',
        stems=('壬', '丙'),
        heading='十月辛金',
        sentence='先用壬水，次取丙火',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='子',
        stems=('壬', '丙'),
        heading='十一月辛金',
        sentence='壬丙两透，不见戊癸，衣锦腰金。',
        later=None,
    ),
    ClimateEntry(
        day_master='辛',
        months='丑',
        stems=('丙', '壬', '戊', '己'),
        heading='十二月辛金',
        sentence='十二月辛金，丙先壬后，戊己次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='寅',
        stems=('庚', '丙', '戊'),
        heading='正月壬水',
        sentence='宜用庚金之源，庶不致汪洋无度。有庚丙戊三者齐透，科甲功名。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='卯',
        stems=('戊', '辛', '庚'),
        heading='二月壬水',
        sentence='二月壬水，先戊后辛，庚金次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='辰',
        stems=('甲', '庚'),
        heading='三月壬水',
        sentence='先用甲疏季土，次取庚金。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='巳',
        stems=('壬', '辛', '庚'),
        heading='四月壬水',
        sentence='专取壬水比肩为助，次取辛金发源，且暗合丙火，庚金为佐。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='午',
        stems=('癸', '庚'),
        heading='五月壬水',
        sentence='五月壬水，丁旺壬弱，取癸为用，取庚为佐。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='未',
        stems=('辛', '甲', '癸'),
        heading='六月壬水',
        sentence='六月壬水，先辛后甲，次取癸水。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='申',
        stems=('戊', '丁'),
        heading='七月壬水',
        sentence='专用戊土，次取丁火佐戊制庚。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='酉',
        stems=('甲', '庚'),
        heading='八月壬水',
        sentence='八月壬水，专用甲木，庚金次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='戌',
        stems=('甲', '丙'),
        heading='九月壬水',
        sentence='九月壬水，专用甲木，次用丙火。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='亥',
        stems=('戊', '丙', '庚'),
        heading='十月壬水',
        sentence='十月壬水、专用戊丙，次取庚金。',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='子',
        stems=('戊', '丙'),
        heading='十一月壬水',
        sentence='先取戊土，次用丙火',
        later=None,
    ),
    ClimateEntry(
        day_master='壬',
        months='丑',
        stems=('丙',),
        heading='十二月壬水',
        sentence='上半月癸辛主事，故旺，专用丙火。',
        later=Later(
            stems=('丙', '甲'),
            sentence='下半月己土主事，故衰。亦用丙火，甲木佐之。',
        ),
    ),
    ClimateEntry(
        day_master='癸',
        months='寅',
        stems=('辛', '庚', '丙'),
        heading='正月癸水',
        sentence='正月癸水，辛金为主，庚金次之，丙亦不可少。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='卯',
        stems=('庚', '辛'),
        heading='二月癸水',
        sentence='专以庚金为用，辛金次之。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='辰',
        stems=('丙',),
        heading='三月癸水',
        sentence='清明后、火气未炽，专用丙火，为阴阳合谐。',
        later=Later(
            stems=('丙', '辛', '甲'),
            sentence='谷雨后，虽用丙火，尚宜辛甲佐之。',
        ),
    ),
    ClimateEntry(
        day_master='癸',
        months='巳',
        stems=('辛',),
        heading='四月癸水',
        sentence='总之四月癸水，专用辛金方妙。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='午',
        stems=('庚', '辛', '壬'),
        heading='五月癸水',
        sentence='五月癸水，庚辛壬参酌并用可也。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='未',
        stems=('庚', '辛'),
        heading='六月癸水',
        sentence='所以专用庚辛。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='申',
        stems=('丁',),
        heading='七月癸水',
        sentence='但庚司令刚锐极矣，必取丁火为用。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='酉',
        stems=('辛', '丙'),
        heading='八月癸水',
        sentence='故取辛金为用，丙火佐之。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='戌',
        stems=('辛', '甲'),
        heading='九月癸水',
        sentence='专用辛金发水之源，要比肩滋甲制戊方妙。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='亥',
        stems=('庚', '辛'),
        heading='十月癸水',
        sentence='宜用庚辛为妙。',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='子',
        stems=('丙', '辛'),
        heading='十一月癸水',
        sentence='专用丙火解冻，庶不致成冰，又要辛金滋扶',
        later=None,
    ),
    ClimateEntry(
        day_master='癸',
        months='丑',
        stems=('丙',),
        heading='十二月癸水',
        sentence='十二月癸水，寒极成冰，万物不能舒泰，宜丙火解冻。',
        later=None,
    ),
)


def _index() -> dict[tuple[str, str], ClimateEntry]:
    found: dict[tuple[str, str], ClimateEntry] = {}
    for entry in TABLE:
        if entry.day_master not in STEMS:
            raise RuntimeError(f'A climate entry is malformed: {entry.heading}')
        halves = [(entry.stems, entry.sentence)]
        if entry.later is not None:
            halves.append((entry.later.stems, entry.later.sentence))
        for stems, sentence in halves:
            if not stems or any(stem not in STEMS for stem in stems):
                raise RuntimeError(f'A climate entry names no stem: {entry.heading}')
            if any(stem not in sentence for stem in stems):
                raise RuntimeError(
                    f'A climate entry names a stem its sentence lacks: {entry.heading}'
                )
        for month in entry.months:
            if month not in BRANCHES:
                raise RuntimeError(f'A climate entry names no month: {entry.heading}')
            key = (entry.day_master, month)
            if key in found:
                raise RuntimeError(f'Two climate entries for {key}.')
            found[key] = entry
    return found


ENTRIES: Final = _index()


def climate_entry(day_master: str, month_branch: str) -> ClimateEntry:
    entry = ENTRIES.get((day_master, month_branch))
    if entry is None:
        raise LookupError(
            f'The climate table has no entry for {day_master} in the {month_branch} '
            'month.'
        )
    return entry


def climate_stems(day_master: str, month_branch: str, second_half: bool) -> list[str]:
    """The stems the text names for this Day Master in this birth month, in order;
    `second_half` when the birth came after the month's middle term."""
    entry = climate_entry(day_master, month_branch)
    if second_half and entry.later is not None:
        return list(entry.later.stems)
    return list(entry.stems)
