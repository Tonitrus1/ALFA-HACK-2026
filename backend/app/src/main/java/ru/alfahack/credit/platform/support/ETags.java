package ru.alfahack.credit.platform.support;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/** Сильный ETag версии вида "v12" и разбор If-Match. */
public final class ETags {

    private static final Pattern VERSION = Pattern.compile("^\"v([0-9]{1,16})\"$");

    private ETags() {
    }

    public static String of(long version) {
        return "\"v" + version + "\"";
    }

    public static long parseIfMatch(String ifMatch) {
        Matcher matcher = ifMatch == null ? null : VERSION.matcher(ifMatch.trim());
        if (matcher == null || !matcher.matches()) {
            throw new ApplicationException(ErrorKind.INVALID_REQUEST, "INVALID_IF_MATCH", "Не удалось определить сохранённую версию данных. Обновите страницу и повторите действие");
        }
        return Long.parseLong(matcher.group(1));
    }
}
