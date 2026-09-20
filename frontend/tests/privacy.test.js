import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

test("Privacy Guard: Teacher pages and components NEVER import or display private NoteVersion or student notes", () => {
  const teacherDir = path.resolve(import.meta.dirname, "../src/pages/teacher");
  const teacherFiles = fs.readdirSync(teacherDir);

  for (const file of teacherFiles) {
    if (file.endsWith(".tsx") || file.endsWith(".ts")) {
      const content = fs.readFileSync(path.join(teacherDir, file), "utf-8");
      assert.ok(
        !content.includes("NoteViewer"),
        `Teacher page ${file} must never import NoteViewer`
      );
      assert.ok(
        !content.includes("NoteVersion"),
        `Teacher page ${file} must never reference NoteVersion`
      );
      assert.ok(
        !content.includes("StudentHistory"),
        `Teacher page ${file} must never reference StudentHistory`
      );
    }
  }

  // Also check AnalyticsCharts component
  const chartsContent = fs.readFileSync(path.resolve(import.meta.dirname, "../src/components/AnalyticsCharts.tsx"), "utf-8");
  assert.ok(!chartsContent.includes("NoteVersion"), "AnalyticsCharts must not reference NoteVersion");
  assert.ok(!chartsContent.includes("StudentHistory"), "AnalyticsCharts must not reference StudentHistory");
  assert.ok(!chartsContent.includes("note.markdown"), "AnalyticsCharts must not display note markdown");
});

test("Student Pages Isolation: Student views render private study materials", () => {
  const notesPageContent = fs.readFileSync(path.resolve(import.meta.dirname, "../src/pages/student/NotesPage.tsx"), "utf-8");
  assert.ok(notesPageContent.includes("NoteViewer"), "NotesPage must render NoteViewer for student");

  const attemptPageContent = fs.readFileSync(path.resolve(import.meta.dirname, "../src/pages/student/AttemptPage.tsx"), "utf-8");
  assert.ok(attemptPageContent.includes("NoteViewer"), "AttemptPage must render NoteViewer upon completion");
});
