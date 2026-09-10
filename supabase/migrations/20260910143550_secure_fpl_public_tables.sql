-- FPL AI Coach: server-side Streamlit access only.
-- Public Data API roles cannot read or modify these tables.

ALTER TABLE public.players ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_gameweek ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prediction_features ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.players FROM anon, authenticated;
REVOKE ALL ON TABLE public.player_gameweek FROM anon, authenticated;
REVOKE ALL ON TABLE public.prediction_features FROM anon, authenticated;
