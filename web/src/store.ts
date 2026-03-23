import { reactive } from "vue";
import { type DataClassification, type DriveResponse, type ProjectResponse } from "./client";

interface FormStateStore {
  hasStartedForm: boolean;
  hasFinishedForm: boolean;
  isCorrectDrive: boolean | null;
  areProjectDetailsCorrect: boolean | null;
  dataClassification: DataClassification | null;
  retentionPeriod: number | null;
  isRetentionPeriodCustom: boolean | null;
  retentionPeriodJustification: string;
}

export const formState: FormStateStore = reactive({
  hasStartedForm: false,
  hasFinishedForm: false,
  isCorrectDrive: null,
  areProjectDetailsCorrect: null,
  dataClassification: null,
  isRetentionPeriodCustom: null,
  retentionPeriod: null,
  retentionPeriodJustification: ""
});

interface ArchiveRequestInfoStore {
  isLoading: boolean;
  error: unknown;
  project: ProjectResponse;
  drive: DriveResponse;
}

export const requestInfo: ArchiveRequestInfoStore = reactive({
  isLoading: false,
  error: undefined,
  project: {
    title: "",
    description: "",
    division: "",
    start_date: "",
    end_date: "",
    id: 0,
    members: [],
    codes: []
  },
  drive: {
    allocated_gb: 0,
    date: "",
    free_gb: 0,
    name: "",
    percentage_used: 0,
    used_gb: 0
  }
});
