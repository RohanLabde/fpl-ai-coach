import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const FPL_BOOTSTRAP_URL =
  "https://fantasy.premierleague.com/api/bootstrap-static/";
const FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/";
const BATCH_SIZE = 250;

type FplEvent = { id: number; finished?: boolean; is_current?: boolean; is_next?: boolean };
type FplTeam = { id: number; name: string };
type FplPlayer = Record<string, unknown>;
type FplFixture = Record<string, unknown>;

function batches<T>(values: T[]): T[][] {
  const result: T[][] = [];
  for (let index = 0; index < values.length; index += BATCH_SIZE) {
    result.push(values.slice(index, index + BATCH_SIZE));
  }
  return result;
}

function numberOrNull(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function currentGameweek(events: FplEvent[]): number | null {
  const current = events.find((event) => event.is_current) ??
    events.find((event) => event.is_next);
  return current?.id ?? null;
}

function latestFinishedGameweek(events: FplEvent[]): number | null {
  const finished = events
    .filter((event) => event.finished)
    .map((event) => event.id);
  return finished.length ? Math.max(...finished) : null;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

Deno.serve(async (request) => {
  if (request.method !== "POST") {
    return Response.json({ error: "POST requests only." }, { status: 405 });
  }

  const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
  const secretKey = secretKeys.default ??
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const supabaseUrl = Deno.env.get("SUPABASE_URL");

  if (!supabaseUrl || !secretKey) {
    return Response.json(
      { error: "Supabase server credentials are not available to this function." },
      { status: 500 },
    );
  }

  const supabase = createClient(supabaseUrl, secretKey);
  let currentGw: number | null = null;
  let finishedGw: number | null = null;

  try {
    const [bootstrapResponse, fixturesResponse] = await Promise.all([
      fetch(FPL_BOOTSTRAP_URL),
      fetch(FPL_FIXTURES_URL),
    ]);
    if (!bootstrapResponse.ok || !fixturesResponse.ok) {
      throw new Error(
        `FPL source request failed: bootstrap=${bootstrapResponse.status}, fixtures=${fixturesResponse.status}`,
      );
    }

    const bootstrap = await bootstrapResponse.json();
    const fixtures = await fixturesResponse.json() as FplFixture[];
    const teams = (bootstrap.teams ?? []) as FplTeam[];
    const players = (bootstrap.elements ?? []) as FplPlayer[];
    const events = (bootstrap.events ?? []) as FplEvent[];
    const teamNames = new Map(teams.map((team) => [team.id, team.name]));
    const positionNames = new Map(
      (bootstrap.element_types ?? []).map((position: Record<string, unknown>) => [
        Number(position.id),
        String(position.singular_name_short ?? position.singular_name ?? ""),
      ]),
    );

    currentGw = currentGameweek(events);
    finishedGw = latestFinishedGameweek(events);
    const snapshotAt = new Date().toISOString();

    const currentPlayers = players.map((player) => ({
      player_id: Number(player.id),
      first_name: String(player.first_name ?? ""),
      second_name: String(player.second_name ?? ""),
      team_id: numberOrNull(player.team),
      team_name: teamNames.get(Number(player.team)) ?? null,
      position: positionNames.get(Number(player.element_type)) ?? null,
      price: numberOrNull(player.now_cost) === null
        ? null
        : Number(player.now_cost) / 10,
      total_points: numberOrNull(player.total_points),
      form: numberOrNull(player.form),
      selected_by_percent: numberOrNull(player.selected_by_percent),
    }));

    const snapshotPlayers = players.map((player) => ({
      snapshot_at: snapshotAt,
      player_id: Number(player.id),
      first_name: String(player.first_name ?? ""),
      second_name: String(player.second_name ?? ""),
      web_name: String(player.web_name ?? ""),
      team_id: numberOrNull(player.team),
      team_name: teamNames.get(Number(player.team)) ?? null,
      position: positionNames.get(Number(player.element_type)) ?? null,
      price: numberOrNull(player.now_cost) === null
        ? null
        : Number(player.now_cost) / 10,
      total_points: numberOrNull(player.total_points),
      form: numberOrNull(player.form),
      selected_by_percent: numberOrNull(player.selected_by_percent),
      status: String(player.status ?? ""),
      chance_of_playing_next_round: numberOrNull(
        player.chance_of_playing_next_round,
      ),
      news: String(player.news ?? ""),
      current_gameweek: currentGw,
    }));

    const fixtureRows = fixtures.map((fixture) => ({
      fixture_id: Number(fixture.id),
      gameweek: numberOrNull(fixture.event),
      kickoff_time: fixture.kickoff_time ?? null,
      started: Boolean(fixture.started),
      finished: Boolean(fixture.finished),
      finished_provisional: Boolean(fixture.finished_provisional),
      home_team_id: numberOrNull(fixture.team_h),
      home_team_name: teamNames.get(Number(fixture.team_h)) ?? null,
      away_team_id: numberOrNull(fixture.team_a),
      away_team_name: teamNames.get(Number(fixture.team_a)) ?? null,
      home_difficulty: numberOrNull(fixture.team_h_difficulty),
      away_difficulty: numberOrNull(fixture.team_a_difficulty),
      updated_at: snapshotAt,
    }));

    for (const batch of batches(currentPlayers)) {
      const { error } = await supabase.from("players").upsert(batch, {
        onConflict: "player_id",
      });
      if (error) throw new Error(`Current player update failed: ${error.message}`);
    }
    for (const batch of batches(snapshotPlayers)) {
      const { error } = await supabase.from("fpl_live_player_snapshots").insert(batch);
      if (error) throw new Error(`Snapshot insert failed: ${error.message}`);
    }
    for (const batch of batches(fixtureRows)) {
      const { error } = await supabase.from("fpl_fixtures").upsert(batch, {
        onConflict: "fixture_id",
      });
      if (error) throw new Error(`Fixture update failed: ${error.message}`);
    }

    const { error: auditError } = await supabase.from("fpl_refresh_runs").insert({
      refresh_type: "live_snapshot",
      status: "completed",
      completed_at: snapshotAt,
      source: "FPL bootstrap-static + fixtures via Edge Function",
      current_gameweek: currentGw,
      latest_finished_gameweek: finishedGw,
      player_snapshot_rows: snapshotPlayers.length,
      fixture_rows: fixtureRows.length,
      message: "Live player snapshot and fixtures refreshed successfully.",
    });
    if (auditError) throw new Error(`Refresh audit failed: ${auditError.message}`);

    return Response.json({
      ok: true,
      snapshot_at: snapshotAt,
      current_gameweek: currentGw,
      latest_finished_gameweek: finishedGw,
      player_snapshot_rows: snapshotPlayers.length,
      fixture_rows: fixtureRows.length,
    });
  } catch (error) {
    await supabase.from("fpl_refresh_runs").insert({
      refresh_type: "live_snapshot",
      status: "failed",
      completed_at: new Date().toISOString(),
      source: "FPL bootstrap-static + fixtures via Edge Function",
      current_gameweek: currentGw,
      latest_finished_gameweek: finishedGw,
      message: errorText(error).slice(0, 1000),
    });
    return Response.json({ error: errorText(error) }, { status: 500 });
  }
});
