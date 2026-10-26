package ru.alfahack.credit.access.infrastructure;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.access.application.ActorView;
import ru.alfahack.credit.access.application.CompanyView;

/** Чтение участников, компаний и членства из схемы access. */
@Repository
public class AccessRepository {

    private static final String COMPANY_SELECT = """
            SELECT c.company_id, c.display_name, c.tax_id, c.source_updated_at,
                   array_agg(m.role ORDER BY m.role) AS roles
            FROM access.company c
            JOIN access.company_membership m ON m.company_id = c.company_id
            """;

    private final JdbcClient jdbc;

    public AccessRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<ActorView> findActor(String actorId) {
        return jdbc.sql("SELECT actor_id, display_name, kind, disabled FROM access.actor WHERE actor_id = :id")
                .param("id", actorId)
                .query((rs, row) -> new ActorView(
                        rs.getString("actor_id"), rs.getString("display_name"),
                        rs.getString("kind"), rs.getBoolean("disabled")))
                .optional();
    }

    public List<ActorView> listActiveRepresentatives() {
        return jdbc.sql("""
                        SELECT actor_id, display_name, kind, disabled FROM access.actor
                        WHERE kind = 'REPRESENTATIVE' AND NOT disabled ORDER BY actor_id LIMIT 100
                        """)
                .query((rs, row) -> new ActorView(
                        rs.getString("actor_id"), rs.getString("display_name"),
                        rs.getString("kind"), rs.getBoolean("disabled")))
                .list();
    }

    /** Компании участника по возрастанию companyId строго после cursor (keyset). */
    public List<CompanyView> companiesOf(String actorId, String afterCompanyId, int limit) {
        return jdbc.sql(COMPANY_SELECT + """
                        WHERE m.actor_id = :actor AND (CAST(:after AS text) IS NULL OR c.company_id > :after)
                        GROUP BY c.company_id
                        ORDER BY c.company_id
                        LIMIT :limit
                        """)
                .param("actor", actorId)
                .param("after", afterCompanyId)
                .param("limit", limit)
                .query((rs, row) -> companyRow(rs))
                .list();
    }

    public Optional<CompanyView> companyOf(String actorId, String companyId) {
        return jdbc.sql(COMPANY_SELECT + """
                        WHERE m.actor_id = :actor AND c.company_id = :company
                        GROUP BY c.company_id
                        """)
                .param("actor", actorId)
                .param("company", companyId)
                .query((rs, row) -> companyRow(rs))
                .optional();
    }

    private static CompanyView companyRow(ResultSet rs) throws SQLException {
        var updated = rs.getTimestamp("source_updated_at");
        return new CompanyView(
                rs.getString("company_id"),
                rs.getString("display_name"),
                rs.getString("tax_id"),
                strings(rs.getArray("roles")),
                updated == null ? null : updated.toInstant());
    }

    private static List<String> strings(Array array) throws SQLException {
        return Arrays.stream((Object[]) array.getArray()).map(String.class::cast).toList();
    }
}
