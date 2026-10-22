package ru.alfahack.credit.workspace.infrastructure;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class FeedRepository {
    private final JdbcClient jdbc;
    public FeedRepository(JdbcClient jdbc) { this.jdbc = jdbc; }
    public JdbcClient sql() { return jdbc; }
    public void lock(String actor, String company) {
        jdbc.sql("SELECT pg_advisory_xact_lock(hashtextextended(:key, 2))")
            .param("key", actor + ":" + company).query((rs, row) -> 1).list();
        jdbc.sql("INSERT INTO workspace.feed_state(actor_id,company_id) VALUES(:a,:c) ON CONFLICT DO NOTHING")
            .param("a",actor).param("c",company).update();
    }
    public Map<String,Object> state(String actor, String company) {
        return jdbc.sql("SELECT *, preferences::text AS preferences_json FROM workspace.feed_state WHERE actor_id=:a AND company_id=:c")
            .param("a",actor).param("c",company).query().singleRow();
    }
    public Optional<Map<String,Object>> page(String cursor, String actor, String company) {
        return jdbc.sql("SELECT *, response::text AS response_json FROM workspace.feed_page WHERE cursor=:id AND actor_id=:a AND company_id=:c")
            .param("id",cursor).param("a",actor).param("c",company).query().listOfRows().stream().findFirst();
    }
    public List<Map<String,Object>> reactions(String actor, String company) {
        return jdbc.sql("SELECT * FROM workspace.feed_reaction WHERE actor_id=:a AND company_id=:c ORDER BY reaction_at DESC, content_id")
            .param("a",actor).param("c",company).query().listOfRows();
    }
}
