--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13
-- Dumped by pg_dump version 15.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: videohelper_user
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO videohelper_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: job_tombstones; Type: TABLE; Schema: public; Owner: videohelper_user
--

CREATE TABLE public.job_tombstones (
    id text NOT NULL,
    reason text,
    deleted_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.job_tombstones OWNER TO videohelper_user;

--
-- Name: jobs; Type: TABLE; Schema: public; Owner: videohelper_user
--

CREATE TABLE public.jobs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    workflow character varying(100) NOT NULL,
    step character varying(100),
    user_id character varying(255),
    request_data jsonb,
    result jsonb,
    resume_data jsonb,
    resumed_from uuid,
    resumed_to jsonb,
    resume_attempt integer DEFAULT 1,
    error_message text,
    logs jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    duration_seconds real
);


ALTER TABLE public.jobs OWNER TO videohelper_user;

--
-- Name: migrations; Type: TABLE; Schema: public; Owner: videohelper_user
--

CREATE TABLE public.migrations (
    revision text NOT NULL,
    applied_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.migrations OWNER TO videohelper_user;

--
-- Name: videos; Type: TABLE; Schema: public; Owner: videohelper_user
--

CREATE TABLE public.videos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    job_id uuid,
    filename character varying(255) NOT NULL,
    file_path text NOT NULL,
    title character varying(255),
    description text,
    duration real,
    file_size bigint,
    thumbnail_path text,
    status character varying(50) DEFAULT 'processing'::character varying,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.videos OWNER TO videohelper_user;

--
-- Data for Name: job_tombstones; Type: TABLE DATA; Schema: public; Owner: videohelper_user
--

COPY public.job_tombstones (id, reason, deleted_at, created_at) FROM stdin;
\.


--
-- Data for Name: jobs; Type: TABLE DATA; Schema: public; Owner: videohelper_user
--

COPY public.jobs (id, status, workflow, step, user_id, request_data, result, resume_data, resumed_from, resumed_to, resume_attempt, error_message, logs, created_at, updated_at, started_at, ended_at, duration_seconds) FROM stdin;
876e59cd-3df7-430f-b88e-2a1016e16c38	error	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://youtube.com/watch?v=test", "maxDuration": 110, "minDuration": 60, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	500: Failed to submit job to video processor	[]	2025-09-27 18:42:32.395855+00	2025-09-27 18:42:32.411573+00	\N	\N	\N
d0e08a8b-c689-46d8-869d-05b48190ff32	queued	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	\N	[]	2025-09-27 21:30:06.652932+00	2025-09-27 21:30:06.652932+00	\N	\N	\N
0a585182-5b31-47c1-a664-a7c7124f66b3	queued	brainrot	init	\N	{"maxReuse": 3, "unlimited": true, "youtubeUrl": "https://www.youtube.com/watch?v=2BiUsiIsI2c", "maxDuration": 30, "minDuration": 20, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	\N	[]	2025-09-27 22:26:31.149891+00	2025-09-27 22:26:31.149891+00	\N	\N	\N
10a7a410-4d81-49b9-b79b-23da1a80b701	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 20:44:15.931343+00	2025-09-27 22:59:37.826742+00	\N	2025-09-27 22:59:37.826296+00	0
a2afedbf-b245-4ce7-964f-1874799493ac	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 20:39:58.45878+00	2025-09-27 22:59:37.835599+00	\N	2025-09-27 22:59:37.826296+00	0
56d8855c-ede1-4f21-b7ef-3978950e1653	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 20:25:17.368582+00	2025-09-27 22:59:37.836278+00	\N	2025-09-27 22:59:37.826296+00	0
7540197f-1896-44c2-aff2-94b52aa14092	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 20:01:44.849024+00	2025-09-27 22:59:37.837113+00	\N	2025-09-27 22:59:37.826296+00	0
8725bd69-d71a-48cb-9570-94263126455a	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 19:41:45.804536+00	2025-09-27 22:59:37.837839+00	\N	2025-09-27 22:59:37.826296+00	0
ed8f47eb-87ec-48f5-be8b-49e8896f0bdb	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 19:10:10.45007+00	2025-09-27 22:59:37.838419+00	\N	2025-09-27 22:59:37.826296+00	0
8bfc39fe-37f1-4f77-a3ab-6956d2d1eb9a	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 19:04:27.651809+00	2025-09-27 22:59:37.838951+00	\N	2025-09-27 22:59:37.826296+00	0
e7436c5d-0bbf-41c4-9b28-9d33aff6f4cd	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 19:03:00.198404+00	2025-09-27 22:59:37.839472+00	\N	2025-09-27 22:59:37.826296+00	0
c0181415-e933-4b52-b0ec-d5af9ee2f41e	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 18:55:04.823455+00	2025-09-27 22:59:37.839979+00	\N	2025-09-27 22:59:37.826296+00	0
4dc7561d-8660-42da-b933-bf1977858e2d	cancelled	brainrot	init	\N	{"maxReuse": 3, "unlimited": false, "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "maxDuration": 60, "minDuration": 30, "numCompilations": 1, "generateNoBackground": true, "blurredPillarboxThreshold": 0.1}	\N	\N	\N	[]	1	Server restart: queued job stale (auto-cancel)	[]	2025-09-27 18:46:16.301788+00	2025-09-27 22:59:37.840718+00	\N	2025-09-27 22:59:37.826296+00	0
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: public; Owner: videohelper_user
--

COPY public.migrations (revision, applied_at) FROM stdin;
0001_add_resume_and_tombstone	2025-09-27 18:22:01.261826+00
\.


--
-- Data for Name: videos; Type: TABLE DATA; Schema: public; Owner: videohelper_user
--

COPY public.videos (id, job_id, filename, file_path, title, description, duration, file_size, thumbnail_path, status, metadata, created_at, updated_at) FROM stdin;
\.


--
-- Name: job_tombstones job_tombstones_pkey; Type: CONSTRAINT; Schema: public; Owner: videohelper_user
--

ALTER TABLE ONLY public.job_tombstones
    ADD CONSTRAINT job_tombstones_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: videohelper_user
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: videohelper_user
--

ALTER TABLE ONLY public.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (revision);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: public; Owner: videohelper_user
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: idx_jobs_created_at; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_jobs_created_at ON public.jobs USING btree (created_at DESC);


--
-- Name: idx_jobs_resume_attempt; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_jobs_resume_attempt ON public.jobs USING btree (resume_attempt);


--
-- Name: idx_jobs_status; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_jobs_status ON public.jobs USING btree (status);


--
-- Name: idx_jobs_updated_at; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_jobs_updated_at ON public.jobs USING btree (updated_at DESC);


--
-- Name: idx_jobs_user_id; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_jobs_user_id ON public.jobs USING btree (user_id);


--
-- Name: idx_jobs_workflow; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_jobs_workflow ON public.jobs USING btree (workflow);


--
-- Name: idx_videos_created_at; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_videos_created_at ON public.videos USING btree (created_at DESC);


--
-- Name: idx_videos_filename; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_videos_filename ON public.videos USING btree (filename);


--
-- Name: idx_videos_job_id; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_videos_job_id ON public.videos USING btree (job_id);


--
-- Name: idx_videos_status; Type: INDEX; Schema: public; Owner: videohelper_user
--

CREATE INDEX idx_videos_status ON public.videos USING btree (status);


--
-- Name: jobs update_jobs_updated_at; Type: TRIGGER; Schema: public; Owner: videohelper_user
--

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: videos update_videos_updated_at; Type: TRIGGER; Schema: public; Owner: videohelper_user
--

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON public.videos FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: videos videos_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: videohelper_user
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

