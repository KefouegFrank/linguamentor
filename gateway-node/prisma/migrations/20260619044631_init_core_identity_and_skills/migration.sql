-- CreateEnum
CREATE TYPE "Language" AS ENUM ('ENGLISH', 'FRENCH');

-- CreateEnum
CREATE TYPE "ProficiencyLevel" AS ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2');

-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "learner_profiles" (
    "id" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "targetLanguage" "Language" NOT NULL,
    "currentLevel" "ProficiencyLevel" NOT NULL DEFAULT 'A1',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "learner_profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "skill_vectors" (
    "id" UUID NOT NULL,
    "profileId" UUID NOT NULL,
    "grammarScore" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "vocabularyScore" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "pronunciationScore" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "coherenceScore" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "skill_vectors_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE UNIQUE INDEX "learner_profiles_userId_key" ON "learner_profiles"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "skill_vectors_profileId_key" ON "skill_vectors"("profileId");

-- AddForeignKey
ALTER TABLE "learner_profiles" ADD CONSTRAINT "learner_profiles_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "skill_vectors" ADD CONSTRAINT "skill_vectors_profileId_fkey" FOREIGN KEY ("profileId") REFERENCES "learner_profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;
