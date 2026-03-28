-- Apply 5-tier pricing model based on avg_points_baseline
-- T1 Elite  (>=40 pts baseline): 30M — franchise players, consistent carry performers
-- T2 Star   (>=33 pts baseline): 25M — strong performers, reliable starters
-- T3 Sólido (>=24 pts baseline): 20M — solid mid-tier, good value picks
-- T4 Regular (>=18 pts baseline): 15M — below average, situational use
-- T5 Flojo  (<18 pts or NULL):   10M — low performers or unproven/no data
UPDATE players
SET current_price = CASE
  WHEN avg_points_baseline >= 40 THEN 30
  WHEN avg_points_baseline >= 33 THEN 25
  WHEN avg_points_baseline >= 24 THEN 20
  WHEN avg_points_baseline >= 18 THEN 15
  ELSE 10
END;
