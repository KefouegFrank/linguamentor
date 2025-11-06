-- CreateEnum
CREATE TYPE "UserRole" AS ENUM ('LEARNER', 'ADMIN', 'TEACHER');

-- CreateEnum
CREATE TYPE "CEFRLevel" AS ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2');

-- CreateEnum
CREATE TYPE "TargetLanguage" AS ENUM ('ENGLISH', 'SPANISH', 'FRENCH', 'GERMAN', 'MANDARIN', 'JAPANESE', 'KOREAN', 'ARABIC', 'PORTUGUESE', 'ITALIAN');

-- CreateEnum
CREATE TYPE "ExamType" AS ENUM ('IELTS', 'TOEFL', 'DELF', 'DELE', 'JLPT', 'HSK', 'CEFR', 'OTHER');

-- CreateEnum
CREATE TYPE "SkillType" AS ENUM ('SPEAKING', 'LISTENING', 'READING', 'WRITING', 'GRAMMAR', 'VOCABULARY', 'PRONUNCIATION');

-- CreateEnum
CREATE TYPE "LessonDifficulty" AS ENUM ('BEGINNER', 'INTERMEDIATE', 'ADVANCED');

-- CreateEnum
CREATE TYPE "SessionType" AS ENUM ('LESSON', 'PRACTICE', 'EXAM', 'CONVERSATION');

-- CreateEnum
CREATE TYPE "SessionStatus" AS ENUM ('IN_PROGRESS', 'COMPLETED', 'ABANDONED');

-- CreateEnum
CREATE TYPE "InteractionType" AS ENUM ('TEXT_INPUT', 'VOICE_INPUT', 'AI_RESPONSE', 'CORRECTION', 'EXPLANATION');

-- CreateEnum
CREATE TYPE "AssessmentType" AS ENUM ('PLACEMENT_TEST', 'MOCK_EXAM', 'QUIZ', 'SKILL_CHECK');

-- CreateEnum
CREATE TYPE "EvaluationCategory" AS ENUM ('GRAMMAR', 'VOCABULARY', 'PRONUNCIATION', 'FLUENCY', 'COHERENCE', 'TASK_ACHIEVEMENT', 'LEXICAL_RESOURCE', 'GRAMMATICAL_RANGE');

-- CreateEnum
CREATE TYPE "FeedbackType" AS ENUM ('GRAMMAR_CORRECTION', 'PRONUNCIATION_TIP', 'VOCABULARY_SUGGESTION', 'FLUENCY_ADVICE', 'GENERAL_COMMENT');

-- CreateEnum
CREATE TYPE "AnalyticsPeriod" AS ENUM ('DAILY', 'WEEKLY', 'MONTHLY', 'ALL_TIME');

-- CreateEnum
CREATE TYPE "AchievementCategory" AS ENUM ('STREAK', 'SKILL_MASTERY', 'EXAM_SUCCESS', 'MILESTONE', 'CONSISTENCY');

-- CreateEnum
CREATE TYPE "ModelProvider" AS ENUM ('OPENAI', 'ANTHROPIC', 'GOOGLE', 'WHISPER', 'ELEVENLABS', 'CUSTOM');

-- CreateEnum
CREATE TYPE "LogLevel" AS ENUM ('INFO', 'WARNING', 'ERROR', 'CRITICAL');

-- CreateTable
CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "first_name" TEXT,
    "last_name" TEXT,
    "role" "UserRole" NOT NULL DEFAULT 'LEARNER',
    "target_language" "TargetLanguage" NOT NULL,
    "native_language" TEXT,
    "current_level" "CEFRLevel" NOT NULL DEFAULT 'A1',
    "target_exam" "ExamType",
    "readiness_score" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_study_time" INTEGER NOT NULL DEFAULT 0,
    "current_streak" INTEGER NOT NULL DEFAULT 0,
    "longest_streak" INTEGER NOT NULL DEFAULT 0,
    "last_active_at" TIMESTAMP(3),
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "email_verified" BOOLEAN NOT NULL DEFAULT false,
    "subscription_tier" TEXT NOT NULL DEFAULT 'free',
    "oauth_provider" TEXT,
    "oauth_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "refresh_tokens" (
    "id" TEXT NOT NULL,
    "token_hash" TEXT NOT NULL,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "revoked" BOOLEAN NOT NULL DEFAULT false,
    "replaced_by_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" TEXT NOT NULL,

    CONSTRAINT "refresh_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "lessons" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "topic" TEXT NOT NULL,
    "skill_type" "SkillType" NOT NULL,
    "difficulty" "LessonDifficulty" NOT NULL,
    "cefr_level" "CEFRLevel" NOT NULL,
    "target_language" "TargetLanguage" NOT NULL,
    "generated_prompt" TEXT,
    "objectives" JSONB,
    "content" JSONB,
    "summary_notes" TEXT,
    "is_completed" BOOLEAN NOT NULL DEFAULT false,
    "completed_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "lessons_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "lesson_id" TEXT,
    "session_type" "SessionType" NOT NULL,
    "status" "SessionStatus" NOT NULL DEFAULT 'IN_PROGRESS',
    "duration_minutes" INTEGER NOT NULL DEFAULT 0,
    "accuracy_score" DOUBLE PRECISION,
    "engagement_score" DOUBLE PRECISION,
    "total_interactions" INTEGER NOT NULL DEFAULT 0,
    "correct_answers" INTEGER NOT NULL DEFAULT 0,
    "incorrect_answers" INTEGER NOT NULL DEFAULT 0,
    "context_data" JSONB,
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ended_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_interactions" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "session_id" TEXT NOT NULL,
    "interaction_type" "InteractionType" NOT NULL,
    "user_input" TEXT,
    "ai_response" TEXT,
    "audio_url" TEXT,
    "transcription" TEXT,
    "is_correct" BOOLEAN,
    "correction_text" TEXT,
    "prompt_context" JSONB,
    "model_metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_interactions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "assessments" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "assessment_type" "AssessmentType" NOT NULL,
    "exam_type" "ExamType",
    "skill_type" "SkillType",
    "total_score" DOUBLE PRECISION NOT NULL,
    "max_score" DOUBLE PRECISION NOT NULL,
    "percentage_score" DOUBLE PRECISION NOT NULL,
    "cefr_level" "CEFRLevel" NOT NULL,
    "reading_score" DOUBLE PRECISION,
    "writing_score" DOUBLE PRECISION,
    "speaking_score" DOUBLE PRECISION,
    "listening_score" DOUBLE PRECISION,
    "overall_feedback" TEXT,
    "strengths" JSONB,
    "weaknesses" JSONB,
    "recommendations" JSONB,
    "duration_minutes" INTEGER,
    "is_passed" BOOLEAN,
    "completed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "assessments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "evaluation_results" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "assessment_id" TEXT,
    "skill_type" "SkillType" NOT NULL,
    "category" "EvaluationCategory" NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    "max_score" DOUBLE PRECISION NOT NULL,
    "rubric_used" TEXT,
    "detailed_feedback" TEXT,
    "error_examples" JSONB,
    "improvement_tips" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "evaluation_results_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "feedbacks" (
    "id" TEXT NOT NULL,
    "session_id" TEXT,
    "assessment_id" TEXT,
    "feedback_type" "FeedbackType" NOT NULL,
    "category" "EvaluationCategory",
    "original_text" TEXT,
    "corrected_text" TEXT,
    "explanation" TEXT NOT NULL,
    "severity" TEXT,
    "is_addressed" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "feedbacks_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "analytics_summaries" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "period" "AnalyticsPeriod" NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "total_sessions" INTEGER NOT NULL DEFAULT 0,
    "total_study_time" INTEGER NOT NULL DEFAULT 0,
    "lessons_completed" INTEGER NOT NULL DEFAULT 0,
    "assessments_taken" INTEGER NOT NULL DEFAULT 0,
    "average_accuracy" DOUBLE PRECISION,
    "current_streak" INTEGER NOT NULL DEFAULT 0,
    "cefr_progress" TEXT,
    "readiness_score" DOUBLE PRECISION,
    "speaking_score" DOUBLE PRECISION,
    "listening_score" DOUBLE PRECISION,
    "reading_score" DOUBLE PRECISION,
    "writing_score" DOUBLE PRECISION,
    "weak_areas" JSONB,
    "strong_areas" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "analytics_summaries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "achievements" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "category" "AchievementCategory" NOT NULL,
    "icon_url" TEXT,
    "current_progress" INTEGER NOT NULL DEFAULT 0,
    "target_progress" INTEGER NOT NULL,
    "is_unlocked" BOOLEAN NOT NULL DEFAULT false,
    "xp_reward" INTEGER,
    "badge_level" TEXT,
    "unlocked_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "achievements_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_model_runs" (
    "id" TEXT NOT NULL,
    "model_provider" "ModelProvider" NOT NULL,
    "model_name" TEXT NOT NULL,
    "model_version" TEXT,
    "endpoint" TEXT NOT NULL,
    "prompt_hash" TEXT,
    "request_payload" JSONB,
    "response_hash" TEXT,
    "response_metadata" JSONB,
    "latency_ms" INTEGER,
    "token_count" INTEGER,
    "estimated_cost" DOUBLE PRECISION,
    "is_success" BOOLEAN NOT NULL DEFAULT true,
    "error_message" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_model_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "admin_logs" (
    "id" TEXT NOT NULL,
    "log_level" "LogLevel" NOT NULL,
    "message" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "user_id" TEXT,
    "session_id" TEXT,
    "ip_address" TEXT,
    "user_agent" TEXT,
    "metadata" JSONB,
    "stack_trace" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "admin_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE INDEX "users_email_idx" ON "users"("email");

-- CreateIndex
CREATE INDEX "users_target_language_idx" ON "users"("target_language");

-- CreateIndex
CREATE INDEX "users_current_level_idx" ON "users"("current_level");

-- CreateIndex
CREATE INDEX "refresh_tokens_user_id_idx" ON "refresh_tokens"("user_id");

-- CreateIndex
CREATE INDEX "refresh_tokens_token_hash_idx" ON "refresh_tokens"("token_hash");

-- CreateIndex
CREATE INDEX "refresh_tokens_expires_at_idx" ON "refresh_tokens"("expires_at");

-- CreateIndex
CREATE INDEX "lessons_user_id_idx" ON "lessons"("user_id");

-- CreateIndex
CREATE INDEX "lessons_skill_type_idx" ON "lessons"("skill_type");

-- CreateIndex
CREATE INDEX "lessons_cefr_level_idx" ON "lessons"("cefr_level");

-- CreateIndex
CREATE INDEX "lessons_is_completed_idx" ON "lessons"("is_completed");

-- CreateIndex
CREATE INDEX "sessions_user_id_idx" ON "sessions"("user_id");

-- CreateIndex
CREATE INDEX "sessions_session_type_idx" ON "sessions"("session_type");

-- CreateIndex
CREATE INDEX "sessions_status_idx" ON "sessions"("status");

-- CreateIndex
CREATE INDEX "sessions_started_at_idx" ON "sessions"("started_at");

-- CreateIndex
CREATE INDEX "ai_interactions_user_id_idx" ON "ai_interactions"("user_id");

-- CreateIndex
CREATE INDEX "ai_interactions_session_id_idx" ON "ai_interactions"("session_id");

-- CreateIndex
CREATE INDEX "ai_interactions_interaction_type_idx" ON "ai_interactions"("interaction_type");

-- CreateIndex
CREATE INDEX "ai_interactions_created_at_idx" ON "ai_interactions"("created_at");

-- CreateIndex
CREATE INDEX "assessments_user_id_idx" ON "assessments"("user_id");

-- CreateIndex
CREATE INDEX "assessments_assessment_type_idx" ON "assessments"("assessment_type");

-- CreateIndex
CREATE INDEX "assessments_exam_type_idx" ON "assessments"("exam_type");

-- CreateIndex
CREATE INDEX "assessments_completed_at_idx" ON "assessments"("completed_at");

-- CreateIndex
CREATE INDEX "evaluation_results_user_id_idx" ON "evaluation_results"("user_id");

-- CreateIndex
CREATE INDEX "evaluation_results_assessment_id_idx" ON "evaluation_results"("assessment_id");

-- CreateIndex
CREATE INDEX "evaluation_results_skill_type_idx" ON "evaluation_results"("skill_type");

-- CreateIndex
CREATE INDEX "evaluation_results_category_idx" ON "evaluation_results"("category");

-- CreateIndex
CREATE INDEX "feedbacks_session_id_idx" ON "feedbacks"("session_id");

-- CreateIndex
CREATE INDEX "feedbacks_assessment_id_idx" ON "feedbacks"("assessment_id");

-- CreateIndex
CREATE INDEX "feedbacks_feedback_type_idx" ON "feedbacks"("feedback_type");

-- CreateIndex
CREATE INDEX "feedbacks_is_addressed_idx" ON "feedbacks"("is_addressed");

-- CreateIndex
CREATE INDEX "analytics_summaries_user_id_idx" ON "analytics_summaries"("user_id");

-- CreateIndex
CREATE INDEX "analytics_summaries_period_idx" ON "analytics_summaries"("period");

-- CreateIndex
CREATE INDEX "analytics_summaries_period_start_idx" ON "analytics_summaries"("period_start");

-- CreateIndex
CREATE UNIQUE INDEX "analytics_summaries_user_id_period_period_start_key" ON "analytics_summaries"("user_id", "period", "period_start");

-- CreateIndex
CREATE INDEX "achievements_user_id_idx" ON "achievements"("user_id");

-- CreateIndex
CREATE INDEX "achievements_category_idx" ON "achievements"("category");

-- CreateIndex
CREATE INDEX "achievements_is_unlocked_idx" ON "achievements"("is_unlocked");

-- CreateIndex
CREATE INDEX "ai_model_runs_model_provider_idx" ON "ai_model_runs"("model_provider");

-- CreateIndex
CREATE INDEX "ai_model_runs_model_name_idx" ON "ai_model_runs"("model_name");

-- CreateIndex
CREATE INDEX "ai_model_runs_is_success_idx" ON "ai_model_runs"("is_success");

-- CreateIndex
CREATE INDEX "ai_model_runs_created_at_idx" ON "ai_model_runs"("created_at");

-- CreateIndex
CREATE INDEX "admin_logs_log_level_idx" ON "admin_logs"("log_level");

-- CreateIndex
CREATE INDEX "admin_logs_category_idx" ON "admin_logs"("category");

-- CreateIndex
CREATE INDEX "admin_logs_user_id_idx" ON "admin_logs"("user_id");

-- CreateIndex
CREATE INDEX "admin_logs_created_at_idx" ON "admin_logs"("created_at");

-- AddForeignKey
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "lessons" ADD CONSTRAINT "lessons_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "lessons"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_interactions" ADD CONSTRAINT "ai_interactions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_interactions" ADD CONSTRAINT "ai_interactions_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assessments" ADD CONSTRAINT "assessments_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "evaluation_results" ADD CONSTRAINT "evaluation_results_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "evaluation_results" ADD CONSTRAINT "evaluation_results_assessment_id_fkey" FOREIGN KEY ("assessment_id") REFERENCES "assessments"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "feedbacks" ADD CONSTRAINT "feedbacks_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "feedbacks" ADD CONSTRAINT "feedbacks_assessment_id_fkey" FOREIGN KEY ("assessment_id") REFERENCES "assessments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "analytics_summaries" ADD CONSTRAINT "analytics_summaries_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "achievements" ADD CONSTRAINT "achievements_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
