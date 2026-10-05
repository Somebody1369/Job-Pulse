from typing import Final

WELCOME: Final = (
    "Привіт! Я JobPulse — стежу за вакансіями на DOU та Djinni і за ринком IT.\n\n"
    "/subscribe — підписатися на нові вакансії\n"
    "/subscriptions — мої підписки\n"
    "/search текст — знайти вакансії\n"
    "/market python — конкуренція та зарплати на Djinni\n"
    "/salary python 3 — зарплати за опитуванням DOU\n"
    "/report — звіт ринку картинкою\n"
    "/weekly — щотижневий звіт у понеділок\n"
    "/forget — видалити мої дані"
)
CHOOSE_SKILLS: Final = "Оберіть навички, які мають бути у вакансії, і натисніть «Готово»."
SKILLS_REQUIRED: Final = "Оберіть хоча б одну навичку."
CHOOSE_REMOTE: Final = "Тільки віддалена робота?"
CHOOSE_SALARY: Final = "Мінімальна зарплата в USD? Вакансії без вказаної зарплати теж надсилатиму."
CHOOSE_EXPERIENCE: Final = "Скільки років досвіду можуть вимагати?"
SUBSCRIPTION_CREATED: Final = "Готово! Надсилатиму нові вакансії за підпискою:"
SUBSCRIPTION_CANCELLED: Final = "Скасовано."
NO_SUBSCRIPTIONS: Final = "Підписок ще немає. Створіть першу командою /subscribe."
SUBSCRIPTION_PAUSED: Final = "на паузі"
SUBSCRIPTION_ACTIVE: Final = "активна"
SUBSCRIPTION_DELETED: Final = "Підписку видалено."
SEARCH_USAGE: Final = "Напишіть, що шукати: /search django remote"
NOTHING_FOUND: Final = "Нічого не знайшов."
MARKET_UNKNOWN: Final = "Не знаю такої категорії. Доступні: {categories}"
MARKET_EMPTY: Final = "Статистики ринку ще немає."
SALARY_USAGE: Final = "Формат: /salary мова [роки досвіду], наприклад /salary python 3"
SALARY_EMPTY: Final = "Немає даних опитування для {language}."
REPORT_EMPTY: Final = "Звіт ще не готовий, спробуйте пізніше."
REPORT_CAPTION: Final = "Ринок IT за даними Djinni та DOU"
WEEKLY_ON: Final = "Щотижневий звіт увімкнено: надсилатиму його щопонеділка."
WEEKLY_OFF: Final = "Щотижневий звіт вимкнено."
FORGET_CONFIRM: Final = "Видалити всі ваші підписки та дані? Скасувати це буде неможливо."
FORGOTTEN: Final = "Усі ваші дані видалено. Повертайтеся будь-коли: /start"
SERVICE_UNAVAILABLE: Final = "Сервіс тимчасово недоступний, спробуйте трохи пізніше."

YES: Final = "Так"
NO: Final = "Ні"
DONE: Final = "Готово"
CANCEL: Final = "Скасувати"
ANY: Final = "Будь-яка"
ANY_EXPERIENCE: Final = "Будь-який"
UP_TO_YEARS: Final = "до {years} р."
REMOTE_ONLY: Final = "Тільки віддалено"
REMOTE_ANY: Final = "Не важливо"
PAUSE: Final = "Пауза"
RESUME: Final = "Відновити"
DELETE: Final = "Видалити"
OPEN: Final = "Відкрити вакансію"
REMOTE: Final = "віддалено"
OFFICE: Final = "офіс"
SALARY_NOT_SPECIFIED: Final = "зарплата не вказана"
CANDIDATES_PER_VACANCY: Final = "кандидатів на вакансію"
SALARY_LABELS: Final = ("25%", "медіана", "75%")
MARKET_COUNTS: Final = "Кандидати: {candidates} · Вакансії: {vacancies}{change}"
MARKET_COMPETITION: Final = "Конкуренція: {competition}"
MARKET_EXPECTED: Final = "Очікування: ${low}–{high}"
MARKET_OFFERED: Final = "Пропозиції: ${low}–{high}"
SALARY_HEADER: Final = "<b>{language}</b>, USD на місяць ({low} / {median} / {high})"
SALARY_RESPONSES: Final = "({responses} відповідей)"
FROM_SALARY: Final = "від ${amount}"
COMMAND_DESCRIPTIONS: Final = (
    ("subscribe", "Підписатися на вакансії"),
    ("subscriptions", "Мої підписки"),
    ("search", "Знайти вакансії"),
    ("market", "Конкуренція та зарплати на Djinni"),
    ("salary", "Зарплати за опитуванням DOU"),
    ("report", "Звіт ринку картинкою"),
    ("weekly", "Увімкнути або вимкнути щотижневий звіт"),
    ("forget", "Видалити мої дані"),
    ("help", "Довідка"),
)
