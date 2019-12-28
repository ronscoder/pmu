var tdcss;
var extraApp = new Vue({
    el: '#filterapp',
    delimiters: ["{:", ":}"],
    data: {
        habid: "",
        habid_exact: "",
        site: null,
        dprData: null,
        surevyQtys: null,
        siteExtra: null,
        progressSites: null,
        progressAddtionalSites: null,
        checkedSiteExtras: [],
        checkedSites: [],
        pickedSite: null,
        ifloading: false,
        district: "",
        division: "",
        village: "",
        output: null,
        summary: null,
        showSummary: false,
        filtervalues: "filter_values",
        status: 'any',
        filterShow: true,
        review: 'any',
        withDoc: 'any',
        cert: 'any',
        survey: 'any',
        msg: [],
        additional: false
    },
    filters: {
        pretty: function (value) {
            return JSON.stringify(JSON.parse(value), null, 2);
        }
    },
    methods: {

        api_deleteDoc: function (to, id) {
            res = confirm("Delete doc?");
            //console.log(res);
            if (res) {
                let url = "/work/api_deleteDoc/" + to + "/" + id;
                axios.get(url).then(response => {
                    console.log(response.data);
                    this.load(1);
                });
            }
            /*
            alert('Delete doc?')
                .then(() => {
                    let url = "/work/api_deleteDoc/" + to + "/" + id;
                    axios.get(url).then(response => {
                        console.log(response.data);
                        this.load(1);
                    });
                });*/

        },
        upload: function (to, id, file) {
            console.log(to, id, file);
            let formdata = new FormData();
            formdata.append("to", to);
            formdata.append("id", id);
            formdata.append("file", file);
            axios.post("{% url 'work:api_uploadDoc' %}", formdata, {
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken')
                }
            }).then(response => {
                console.log(response.data);
                this.load(1);
            });

        },
        test: function (v) {
            console.log(v)
        },
        load: function (i) {
            this.site = null;
            this.dprData = null;
            this.siteExtra = null;
            this.surevyQtys = null;
            this.progressSites = null;
            this.progressAddtionalSites = null;
            this.checkedSiteExtras = [];
            this.checkedSites = [];
            this.pickedSite = null;
            this.ifloading = true;
            this.output = null;
            this.summary = null;
            let formdata = new FormData();
            formdata.append('habid', this.habid.replace(" ", ""));
            formdata.append('habid_exact', this.habid_exact.replace(" ", ""));
            formdata.append('district', this.district);
            formdata.append('division', this.division);
            formdata.append('village', this.village);
            console.log(this.status);
            if (!(this.status == 'any')) {
                formdata.append('status', this.status);
            }
            if (!(this.review == 'any')) {
                formdata.append('review', this.review);
            }
            if (!(this.withDoc == 'any'))
                formdata.append('with_doc', this.withDoc);
            if (!(this.cert == 'any'))
                formdata.append('cert', this.cert);

            if (!(this.survey == 'any'))
                formdata.append('survey', this.survey);
            if(this.additional)
                formdata.append('additional', this.additional?"additional":null);

            //this.filtervalues = [this.district, this.division, this.village, this.habid, this.habid_exact, this.status, this.review].map((f) => f ? "(Object.keys({f})[0]-f)" : "");

            //this.filtervalues = this.district + this.division + this.village + this.habid + this.habid_exact + this.status, this.review;
            this.filtervalues = [this.district, this.division, this.village, this.habid, this.habid_exact, this.status, this.review, this.withDoc, this.survey].map(f => (f == "" || f == null) ? "" : `${f}`).join("_");
            formdata.append('filtername', this.filtervalues);
            axios.post("{% url 'work:api_getSite' %}", formdata, {
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken')
                }
            }).then(response => {
                this.ifloading = false;
                //data = JSON.parse(response.data);
                data = response.data;
                this.site = data['site'];
                this.dprData = data['dprData'];
                this.siteExtra = data['siteAdditional'];
                this.surevyQtys = data['surevyQtys'];
                this.progressSites = data['progressSites'];
                this.progressAddtionalSites = data['progressAddtionalSites'];
                this.summary = data['summary'];
                tdcss();
                //this.filterShow = false;
            });
        },
        markVaration: function () {
            let formdata = new FormData();
            formdata.append('pickedSite', this.pickedSite);
            formdata.append('checkedSites', this.checkedSiteExtras);
            axios.post("{% url 'work:api_markVariations' %}", formdata, {
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken')
                }
            }).then(response => {
                this.load();
                console.log(response.data)
            });
        },
        markSiteOrigin: function () {
            let formdata = new FormData();
            formdata.append('pickedSite', this.pickedSite);
            formdata.append('checkedSites', this.checkedSites);
            axios.post("{% url 'work:api_markSiteOrigin' %}", formdata, {
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken')
                }
            }).then(response => {
                this.load();
                console.log(response.data)
            });
        },
        mergeToSite: function () {
            //console.log(this.checkedSiteExtras)
            let formdata = new FormData();
            formdata.append('checkedSites', this.checkedSiteExtras);
            axios.post("{% url 'work:api_mergeToSite' %}", formdata, {
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken')
                }
            }).then(response => {
                this.output = response.data['status']
                this.load();
            });
        },
        updateField: function (field, value, pid, isAdditional) {
            console.log(field, value);
            let formdata = new FormData();
            formdata.append('value', value);
            formdata.append('field', field);
            formdata.append('pid', pid);
            formdata.append('isAdditional', isAdditional);
            axios.post("{% url 'work:api_updateExecQty' %}", formdata, {
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken')
                }
            }).then(response => {
                console.log(response.data);
                this.output = response.data['msg'];
            });
        },
    },
})