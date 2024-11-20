<template>
    <main>
        <div class="title-section">
            <h1 class="app-title">Archive your research drive</h1>
            <h2 class="page-title">How sensitive are the files in your drive?</h2>
            <p>Choose a data classification that best fits the files in your drive. If some files are more sensitive than others, choose the more restrictive classification. Consult the <a href="https://research-hub.auckland.ac.nz/article/research-data-classification" class="btn-link" target="_blank">Research data classification standard</a> for further guidance.</p>
        </div>
        <form>
            <input name="dc" type="radio" id="public-dc">
            <label for="public-dc"><strong>Public</strong> <p>These files are public and do not have a restricted audience. For example, published research data.</p></label>
            <input name="dc" type="radio" id="internal-dc">
            <label for="internal-dc"><strong>Internal</strong>
                <p>These files have a restricted audience. For example, research data that are intended for publication at a later stage.</p>
            </label>
               <input name="dc" type="radio" id="sensitive-dc">
                <label for="sensitive-dc"><strong>Sensitive</strong>
                    <p>
                        These files have a highly restricted audience. For example, research data that are commercially sensitive, subject to human ethics approval, or subject to contracts for development of national or international defence.
                    </p>
                </label>
                <input name="dc" type="radio" id="restricted-dc">
                <label for="restricted-dc"><strong>Restricted</strong> <p>
                    Access to these files is limited to specific individuals approved by the University Custodian (or nominee). This classification of data as Restricted Data is made by the University Custodian.
                </p>
            </label>
        </form>
        <section class="forward-btn">
      <RouterLink to="/retention-period" class="btn btn-primary">Continue</RouterLink>
    </section>

    </main>
</template>

<style scoped>
form {
    margin-top: 1rem;
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 1rem;
    align-items:center;
}

input {
    height: 1.5rem;
    width: 1.5rem;
}

</style>