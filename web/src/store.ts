import { reactive } from 'vue';
import { type DataClassification, type InputDriveOffboardSubmission, type ProjectChanges, type ProjectWithDriveMember, type ResearchDriveService } from './client';

interface FormStateStore {
    hasStartedForm: boolean;
    hasFinishedForm: boolean;
    isCorrectDrive: boolean | null;
    areProjectDetailsCorrect: boolean | null;
    projectChanges: ProjectChanges;
    dataClassification: DataClassification | null;
    retentionPeriod: number | null;
    isRetentionPeriodCustom: boolean | null;
}

export const formState: FormStateStore = reactive({
    hasStartedForm: false,
    hasFinishedForm: false,
    isCorrectDrive: null,
    areProjectDetailsCorrect: null,
    projectChanges: {},
    dataClassification: null,
    isRetentionPeriodCustom: null,
    retentionPeriod: null
});

interface ArchiveRequestInfoStore {
    isLoading: boolean,
    error: any,
    project: ProjectWithDriveMember,
    drive: ResearchDriveService
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
        research_drives: [],
        members: [],
        codes: []
    },
    drive: {
        allocated_gb: 0,
        date: "",
        first_day: "",
        last_day: "",
        free_gb: 0,
        name: "",
        percentage_used: 0,
        used_gb: 0
    }
}) 