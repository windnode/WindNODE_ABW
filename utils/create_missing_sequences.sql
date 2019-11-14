-- Create missing sequences
CREATE SEQUENCE stemp_abw_demandts_id_seq
  INCREMENT 1
  START 1;
ALTER TABLE stemp_abw_demandts_id_seq
  OWNER TO windnode;

CREATE SEQUENCE stemp_abw_feedints_id_seq
  INCREMENT 1
  START 1;
ALTER TABLE stemp_abw_feedints_id_seq
  OWNER TO windnode;


-- Set sequence nextval to highest number + 1
SELECT setval('stemp_abw_demandts_id_seq',  (SELECT MAX(id)+1 FROM wn_abw_demandts));
SELECT setval('stemp_abw_feedints_id_seq',  (SELECT MAX(id)+1 FROM wn_abw_feedints));