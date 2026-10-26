package ru.alfahack.credit.support;

/** JSON-тела запросов applications. */
public final class Bodies {

    private Bodies() {
    }

    public static String create(String companyId, long amountMinor, int termMonths) {
        return """
                {"companyId":"%s","productId":"working-capital","productVersion":1,
                 "need":{"purpose":"Закупка товара","amount":{"amountMinor":%d,"currency":"RUB"},"termMonths":%d}}
                """.formatted(companyId, amountMinor, termMonths);
    }

    public static String submit(long expectedVersion, long financialStatementVersion) {
        return """
                {"expectedVersion":%d,"consentRecordIds":[],"documentIds":[],"documentReferences":[],
                 "requirementsVersion":1,"financialStatementVersion":%d}
                """.formatted(expectedVersion, financialStatementVersion);
    }
}
