import { reactive } from 'vue';
import { makeProject, type Project } from './project';
import { getDrive } from "./fixtures"
import { type DataClassification, type InputDriveOffboardSubmission } from './client';

interface FormStateStore {
    hasStartedForm: boolean;
    hasFinishedForm: boolean;
    isCorrectDrive: boolean | null;
    areProjectDetailsCorrect: boolean | null;
    project: Project;
    dataClassification: DataClassification | null;
    retentionPeriod: number | null;
    isRetentionPeriodCustom: boolean | null;
    getSubmission: () => InputDriveOffboardSubmission | null;
}

export const formState: FormStateStore = reactive({
    hasStartedForm: false,
    hasFinishedForm: false,
    isCorrectDrive: null,
    areProjectDetailsCorrect: null,
    project: makeProject(),
    dataClassification: null,
    isRetentionPeriodCustom: null,
    retentionPeriod: null,
    getSubmission: function () {
        if (!this.dataClassification || !this.retentionPeriod) {
            return null;
        } else {
            return {
                dataClassification: this.dataClassification,
                retentionPeriodYears: this.retentionPeriod,
                isCompleted: true,
                driveName: getDrive().name,
                projectChanges: {
                    title: this.project.title,
                    description: this.project.description
                }
            }
        }
    }
});