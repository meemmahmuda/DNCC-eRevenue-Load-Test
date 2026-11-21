import re

from bs4 import BeautifulSoup
from locust import HttpUser, task, between

USERNAME = "######"
PASSWORD = "######"

DNCC_UNLOCK_AUTHORIZED = "YES"
DNCC_CUSERID = "Mahmuda"

FIXED_OTP = "######"  

DASHBOARD_MARKERS = ["logout", USERNAME.lower()]

SAVE_FIRST_LOGIN_FAIL = True
_saved_fail = {"done": False}


def hidden_fields(html):
    """ASP.NET hidden fields (__VIEWSTATE, __EVENTVALIDATION)"""
    soup = BeautifulSoup(html or "", "html.parser")
    return {
        x["name"]: x.get("value", "")
        for x in soup.select("input[type=hidden][name]")
    }


def page_messages(html):
    """Extract messages from HTML page (alert() or error divs)"""
    soup = BeautifulSoup(html or "", "html.parser")
    msgs = []

   
    for s in soup.find_all("script"):
        for m in re.findall(r"alert\(\s*['\"](.+?)['\"]\s*\)", s.get_text() or ""):
            msgs.append("alert: " + m[:150])

    selectors = (
        "[id*=lbl], [id*=Lbl], [id*=msg], [id*=Msg], [id*=err], [id*=Err], "
        ".alert, .error, .text-danger, .validation-summary-errors"
    )
    for t in soup.select(selectors):
        txt = t.get_text(" ", strip=True)
        if txt and txt not in msgs:
            msgs.append(txt[:120])

    if not msgs:
        title = soup.title.get_text(strip=True) if soup.title else ""
        msgs.append(f"no message found, title={title[:60]}")
    return msgs[:3]


def save_first_fail(html):
    if SAVE_FIRST_LOGIN_FAIL and not _saved_fail["done"]:
        _saved_fail["done"] = True
        try:
            with open("fail04.html", "w", encoding="utf-8") as f:
                f.write(html or "")
        except Exception:
            pass


def bad(resp):
    """Connection error / timeout (status 0) or HTTP error = True."""
    return resp is None or resp.status_code == 0 or resp.status_code >= 400


class DNCCUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def login(self):

        # 01 - Unlock user
        if DNCC_UNLOCK_AUTHORIZED == "YES":
            self.client.get(
                "/web/userulocknew.aspx",
                params={"cuserid": DNCC_CUSERID},
                name="01 - Unlock User - GET /web/userulocknew.aspx",
            )

        # 02 - Load login form
        r = self.client.get(
            "/newv/Default",
            name="02 - Load Login Form - GET /newv/Default",
        )
        if bad(r):
            return
        data = hidden_fields(r.text)

        # 03 - Select wing and gender
        data.update({
            "__EVENTTARGET": "ddType",
            "ddType": "b",
            "ddlGender": "0",
        })
        r = self.client.post(
            "/newv/Default",
            data=data,
            name="03 - Select Dropdowns - POST /newv/Default",
        )
        if bad(r):
            return
        data = hidden_fields(r.text)

        # 04 - Submit login credentials
        data.update({
            "ddType": "b",
            "ddlGender": "1",
            "txtLogin": USERNAME,
            "txtPwd": PASSWORD,
            "btnSubmit": "LOGIN",
        })

        with self.client.post(
            "/newv/Default",
            data=data,
            allow_redirects=False,
            name="04 - Submit Login Credentials - POST /newv/Default",
            catch_response=True,
        ) as resp:
            if resp.status_code == 0:
                resp.failure(f"Connection error: {resp.error}")
                return
            location = resp.headers.get("Location", "")
            if "otpverification" in location.lower():
                resp.success()
            else:
                save_first_fail(resp.text)
                resp.failure(
                    f"Login failed: status={resp.status_code}, "
                    f"msg={page_messages(resp.text)}"
                )
                return

        # 05 - Open OTP page
        otp_page = self.client.get(
            location,
            name="05 - Open OTP Page - GET /newv/otpverification.aspx",
        )
        if bad(otp_page) or not otp_page.url:
            return
        otp_data = hidden_fields(otp_page.text)

        otp_data.update({
            "txtOTP": FIXED_OTP,
            "btnSubmit": "VERIFY",
        })

        # 06 - Verify OTP
        with self.client.post(
            otp_page.url,
            data=otp_data,
            allow_redirects=False,
            name="06 - Verify OTP - POST /newv/otpverification.aspx",
            catch_response=True,
        ) as resp:
            if resp.status_code == 0:
                resp.failure(f"Connection error: {resp.error}")
                return
            loc = (resp.headers.get("Location") or "").lower()

            if (
                resp.status_code in (301, 302, 303)
                and loc
                and "otpverification" not in loc
                and "default" not in loc
            ):
                resp.success()
            else:
                resp.failure(
                    f"OTP verify failed: status={resp.status_code}, "
                    f"location={loc}, msg={page_messages(resp.text)}"
                )
                return

        # 07 - Dashboard
        with self.client.get(
            "/newv/web/homenew_ver2",
            allow_redirects=False,
            name="07 - Access Dashboard - GET /newv/web/homenew_ver2",
            catch_response=True,
        ) as dash:
            if dash.status_code == 0:
                dash.failure(f"Connection error: {dash.error}")
                return

            if dash.status_code in (301, 302, 303):
                dash.failure(
                    "Session invalid, redirected to: "
                    f"{dash.headers.get('Location', '')}"
                )
                return

            body = (dash.text or "").lower()
            marker_found = any(m in body for m in DASHBOARD_MARKERS)

            if dash.status_code == 200 and marker_found:
                dash.success()
            else:
                dash.failure(
                    f"Dashboard marker not found: status={dash.status_code}"
                )