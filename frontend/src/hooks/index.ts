/**
 * React hooks for interacting with Synapse API.
 * Authoritative contract: Contracts.md Sections C.4, D.9.
 */
import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import {
  ClassAnalytics,
  ConceptNode,
  GraphEdge,
  NoteVersion,
  PendingTagsResponse,
  SubmitAttemptResponse,
  Test,
} from "../types/synapse";

export function useConcepts() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createConcept = async (markdown: string, conceptName: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.createConcept({ markdown, concept_name: conceptName });
      return res;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { createConcept, loading, error };
}

export function useTagConfirmation(runId: string) {
  const [pending, setPending] = useState<PendingTagsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let isMounted = true;
    apiClient
      .getPendingTags(runId)
      .then((data) => {
        if (isMounted) {
          setPending(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [runId]);

  const confirmTags = async (editedConcepts?: ConceptNode[]) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiClient.confirmTags(runId, {
        run_id: runId,
        confirmed: true,
        edited_concepts: editedConcepts,
      });
      return res;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setSubmitting(false);
    }
  };

  return { pending, loading, submitting, error, confirmTags };
}

export function useAnalytics(conceptId: string) {
  const [analytics, setAnalytics] = useState<ClassAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conceptId) return;
    apiClient
      .getTeacherAnalytics(conceptId)
      .then((res) => {
        setAnalytics(res.analytics);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [conceptId]);

  return { analytics, loading, error };
}

export function useAttempt(testId: string) {
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitAttemptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submitAnswers = async (answers: Record<string, string>) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiClient.submitAttempt({ test_id: testId, answers });
      setResult(res);
      return res;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setSubmitting(false);
    }
  };

  return { submitAnswers, submitting, result, error };
}

export function useNotes(conceptId: string) {
  const [notes, setNotes] = useState<NoteVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conceptId) return;
    apiClient
      .getStudentNotes(conceptId)
      .then((res) => {
        setNotes(res.notes);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [conceptId]);

  return { notes, loading, error };
}

export function useGraph() {
  const [nodes, setNodes] = useState<ConceptNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .getStudentGraph()
      .then((res) => {
        setNodes(res.nodes);
        setEdges(res.edges);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return { nodes, edges, loading, error };
}
