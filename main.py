import os
import PyPDF2
import random
import itertools
import streamlit as st
from io import StringIO
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.retrievers import SVMRetriever
from langchain.chains import QAGenerationChain
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import pandas as pd
from langchain.callbacks.base import CallbackManager
from langchain.embeddings import HuggingFaceEmbeddings
import langchain.callbacks.base


chunk_size = 1000
questions = [
    [
        "what type of document is this? Answer in this format doctype{'document type'} Example: doctype{'invoice'}",
        "doctype",
    ],
    [
        "Issue date between brackets '{ }' Example: date{'13-02-2021'} ",
        "date",
    ],
    [
        "what is the name of the company issuing it? Answer in this format company{'company name'} Example: company{'Google Inc.'}",
        "company",
    ],
    [
        "what is the C.I.F. on NIF? Use this format: cif{'cif'} Example: cif{'B-85638456'}",
        "cif",
    ],
    [
        "what is the invoice number? Use this format: invoicenum{'id number1'} Example: invoicenum{'153RF45'}",
        "invoicenum",
    ],
    [
        "what is the total amount? Use this format: amount{'total amount'}, currency{'currency'} Example amount{'500'}, currency{'$'}",
        ["currency", "amount"],
    ],
    [
        "which bank account should the payment be sent to? Use this format: bank{'number'} Example: bank{'ES23-2355-6345-346747'}",
        "bank",
    ],
    [
        "write a short description of the service or good being billed. If not clear, answer 'Not Clear'",
        "description",
    ],
]


st.set_page_config(page_title="Invoice creator", page_icon=":receipt:", layout="wide")

# 0 = question, 1 = code, 2 = answer
def invoice_table(answers):
    invoice_table = []
    for answer in answers:
        if len(answer[1]) == 2:
            for i in range(len(answer[1])):
                invoice_table.append(
                    (answer[1][i - 1], unwrapper(answer[2], answer[1][i - 1]))
                )
        else:
            invoice_table.append((answer[1], unwrapper(answer[2], answer[1])))
    return invoice_table


def table_format(list):
    first_col = []
    sec_col = []
    for line in list:
        first_col.append(line[0])
        sec_col.append(line[1])
    tabled_list = pd.DataFrame(
        {
            "Data": first_col,
            "Value": sec_col,
        }
    )
    return tabled_list


def unwrapper(text, code_text):
    if "{" in text:
        text = "-" + text + "-"
        print("printed text pre split: ")
        print(text.split(code_text + "{"))
        no, sub1 = text.split(code_text + "{", 1)
        sub2, no = sub1.split("}", 1)
        unwrapped_text = sub2.replace("'", "")
    else:
        unwrapped_text = text
    return unwrapped_text


def invoice_question_list(questions, qa_retrieval):
    answers = []
    for question in questions:
        answers.append((question[0], question[1], qa_retrieval.run(question[0])))
    return answers


@st.cache_data
def load_docs(files):
    st.write("`Reading doc ...`")
    all_text = ""
    for file_path in files:
        file_extension = os.path.splitext(file_path.name)[1]
        if file_extension == ".pdf":
            pdf_reader = PyPDF2.PdfReader(file_path)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            all_text += text
        elif file_extension == ".txt":
            stringio = StringIO(file_path.getvalue().decode("utf-8"))
            text = stringio.read()
            all_text += text
        else:
            st.warning("Please provide txt or pdf.", icon="⚠️")
    return all_text


@st.cache_resource
def create_retriever(_embeddings, splits, retriever_type):
    if retriever_type == "SIMILARITY SEARCH":
        try:
            vectorstore = FAISS.from_texts(splits, _embeddings)
        except (IndexError, ValueError) as e:
            st.error(f"Error creating vectorstore: {e}")
            return
        retriever = vectorstore.as_retriever(k=5)
    elif retriever_type == "SUPPORT VECTOR MACHINES":
        retriever = SVMRetriever.from_texts(splits, _embeddings)

    return retriever


@st.cache_resource
def split_texts(text, chunk_size, overlap, split_method):

    # Split texts
    # IN: text, chunk size, overlap, split_method
    # OUT: list of str splits

    st.write("`Splitting doc ...`")

    split_method = "RecursiveTextSplitter"
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    )

    splits = text_splitter.split_text(text)
    if not splits:
        st.error("Failed to split document")
        st.stop()

    return splits


@st.cache_data
def generate_eval(text, N, chunk):

    # Generate N questions from context of chunk chars
    # IN: text, N questions, chunk size to draw question from in the doc
    # OUT: eval set as JSON list

    st.info("`Generating sample questions ...`")
    n = len(text)
    starting_indices = [random.randint(0, n - chunk) for _ in range(N)]
    sub_sequences = [text[i : i + chunk] for i in starting_indices]
    chain = QAGenerationChain.from_llm(ChatOpenAI(temperature=0))
    eval_set = []
    for i, b in enumerate(sub_sequences):
        try:
            qa = chain.run(b)
            eval_set.append(qa)
            st.write("Creating Question:", i + 1)
        except:
            st.warning("Error generating question %s." % str(i + 1), icon="⚠️")
    eval_set_full = list(itertools.chain.from_iterable(eval_set))
    return eval_set_full


def main_old():

    foot = f"""
    <div style="
        position: fixed;
        bottom: 0;
        left: 30%;
        right: 0;
        width: 50%;
        padding: 0px 0px;
        text-align: center;
    ">
        <p>Spathios</p>
    </div>
    """

    st.markdown(foot, unsafe_allow_html=True)

    # Add custom CSS

    start_html = (
        """
        <style>
            
            MainMenu {visibility: visible;
            }
        
            footer {visibility: hidden;
            }
            .css-card {
                border-radius: 0px;
                padding: 30px 10px 10px 10px;
                background-color: #f8f9fa;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                margin-bottom: 10px;
                font-family: "IBM Plex Sans", sans-serif;
            }
            
            .card-tag {
                border-radius: 0px;
                padding: 1px 5px 1px 5px;
                margin-bottom: 10px;
                position: absolute;
                left: 0px;
                top: 0px;
                font-size: 0.6rem;
                font-family: "IBM Plex Sans", sans-serif;
                color: white;
                background-color: green;
                }
                
            .css-zt5igj {left:0;
            }
            
            span.css-10trblm {margin-left:0;
            }
            
            div.css-1kyxreq {margin-top: -40px;
            }
            
           
       
            
          

        </style>
        """,
    )
    # st.markdown(start_html, unsafe_allow_html=True)
    st.image("https://app.spathios.com/images/spathios_logo.svg")

    second_html = f"""
    <div style="display: flex; align-items: center; margin-left: 0;">
        <h2 style="display: inline-block;">Spathios Invoice Generator</h2>
        <sub style="margin-left:55px;font-size:small; color: green;">   beta</sub>
    </div>
    """
    # st.write(second_html, unsafe_allow_html=True)

    # st.write(
    #    f"""
    # <div style="display: flex; align-items: center; margin-left: 0;">
    #    <h5 style="display: inline-block;">An autonomous invoice generator</h1>
    # </div>
    # """,
    #    unsafe_allow_html=True,
    # )

    # st.sidebar.title("AI")

    embedding_option = st.sidebar.radio(
        "Choose Embeddings", ["OpenAI Embeddings", "HuggingFace Embeddings(slower)"]
    )

    retriever_type = st.sidebar.selectbox(
        "Choose Retriever", ["SIMILARITY SEARCH", "SUPPORT VECTOR MACHINES"]
    )

    # Use RecursiveCharacterTextSplitter as the default and only text splitter
    splitter_type = "RecursiveCharacterTextSplitter"

    # OPENAI_API_KEY Management
    if "openai_api_key" not in st.session_state:
        # openai_api_key = st.text_input(
        #    "Please enter your OpenAI API key or [get one here](https://platform.openai.com/account/api-keys)",
        #    value="",
        #    placeholder="Enter the OpenAI API key which begins with sk-",
        # )
        openai_api_key = st.secrets["OPENAI_API_KEY"]
        if openai_api_key:
            st.session_state.openai_api_key = openai_api_key
            os.environ["OPENAI_API_KEY"] = openai_api_key
        else:
            # warning_text = 'Please enter your OpenAI API key. Get yours from here: [link](https://platform.openai.com/account/api-keys)'
            # warning_html = f'<span>{warning_text}</span>'
            # st.markdown(warning_html, unsafe_allow_html=True)
            return
    else:
        os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key

    uploaded_files = st.file_uploader(
        "", type=["pdf", "txt"], accept_multiple_files=True
    )

    if uploaded_files:
        # Check if last_uploaded_files is not in session_state or if uploaded_files are different from last_uploaded_files
        if (
            "last_uploaded_files" not in st.session_state
            or st.session_state.last_uploaded_files != uploaded_files
        ):
            st.session_state.last_uploaded_files = uploaded_files
            if "eval_set" in st.session_state:
                del st.session_state["eval_set"]

        # Load and process the uploaded PDF or TXT files.
        loaded_text = load_docs(uploaded_files)
        st.toast("Documents uploaded and processed.")

        # Split the document into chunks
        splits = split_texts(
            loaded_text, chunk_size=chunk_size, overlap=0, split_method=splitter_type
        )

        # Display the number of text chunks
        num_chunks = len(splits)
        st.write(f"Number of text chunks: {num_chunks}")

        # Embed using OpenAI embeddings
        # Embed using OpenAI embeddings or HuggingFace embeddings
        if embedding_option == "OpenAI Embeddings":
            embeddings = OpenAIEmbeddings()
        elif embedding_option == "HuggingFace Embeddings(slower)":
            # Replace "bert-base-uncased" with the desired HuggingFace model
            embeddings = HuggingFaceEmbeddings()

        retriever = create_retriever(embeddings, splits, retriever_type)

        # Initialize the RetrievalQA chain with streaming output
        callback_handler = StreamingStdOutCallbackHandler()
        callback_manager = CallbackManager([callback_handler])

        chat_openai = ChatOpenAI(
            streaming=True,
            callback_manager=callback_manager,
            verbose=True,
            temperature=0,
        )
        qa = RetrievalQA.from_chain_type(
            llm=chat_openai, retriever=retriever, chain_type="stuff", verbose=True
        )

        # MEEEEEE
        answers = invoice_question_list(questions, qa)
        inv_table = invoice_table(answers)

        st.write(table_format(inv_table))

        st.write("Ready to answer questions.")
        # Question and answering
        user_question = st.text_input("Enter your question:")
        if user_question:
            answer = qa.run(user_question)
            st.write("Answer:", answer)
        with st.expander("Doc"):
            st.write(questions)
            st.divider()
            st.write(loaded_text)


######################## Spathios
service_types = ["Venue", "Catering", "Transport", "Audiovisual equipment"]
people_based_service_types = ["Venue", "Catering", "Transport"]
vat = {
    "Venue": 0.21,
    "Catering": 0.21,
    "Transport": 0.21,
    "Audiovisual equipment": 0.21,
}
currencies = ["Euro €", "Sterling £"]
MANAGEMENT_FEE = 0.03
general_vat = 0.21
pricing_options = ["by hour", "by number of people", "fixed price"]


def init_session():
    if "num_lines" not in st.session_state:
        st.session_state["num_lines"] = 0
    if "line" not in st.session_state:
        st.session_state["line"] = []
    if "service_type_dropdown" not in st.session_state:
        st.session_state["service_type_dropdown"] = "Venue"


# ...
def add_line():
    c1aux, c2aux, c3aux = st.columns([1, 1, 1])
    with c1aux:
        service_type = st.selectbox(
            "Type of service",
            options=service_types,
            placeholder="Select service type",
        )
    with c2aux:
        pricing_type = st.selectbox("Pricing type: ", options=pricing_options)

    with c3aux:
        st.write("")
        st.write("")
        vat_included = st.checkbox("VAT included in customer price?")

    if st.session_state["service_type_dropdown"] != service_type:
        st.session_state["service_type_dropdown"] = service_type
        st.experimental_rerun()
    with st.form("New line"):

        if pricing_type == "by number of people":
            c2, c3, c4 = st.columns([1, 1, 1])
            with c2:
                num_people = st.number_input("Number of people:", step=1, min_value=1)
            with c3:
                price_per_person = st.number_input(
                    "Customer price per person", min_value=0
                )
            with c4:
                currency = st.selectbox("Currency", options=currencies)

            d1, d2 = st.columns([3, 1])
            with d1:
                discount = st.slider("Discount %", min_value=0, max_value=100, value=0)
            with d2:
                spathios_fee = st.number_input(
                    "Fee %", min_value=0.00, max_value=20.00, value=14.5
                )
        elif pricing_type == "by hour":
            c2, c3, c4 = st.columns([1, 1, 1])
            with c2:
                num_people = st.number_input("Number of hours:", step=1, min_value=1)
            with c3:
                price_per_person = st.number_input("Price per hour", min_value=0)
            with c4:
                currency = st.selectbox("Currency", options=currencies)

            d1, d2 = st.columns([3, 1])
            with d1:
                discount = st.slider("Discount %", min_value=0, max_value=100, value=0)
            with d2:
                spathios_fee = st.number_input(
                    "Fee %", min_value=0.00, max_value=20.00, value=14.5
                )
        elif pricing_type == "fixed price":
            c3, c4 = st.columns([1, 1])
            num_people = 1
            with c3:
                price_per_person = st.number_input("Customer price", min_value=0)
            with c4:
                currency = st.selectbox("Currency", options=currencies)
            d1, d2 = st.columns([3, 1])
            with d1:
                discount = st.slider("Discount %", min_value=0, max_value=100, value=0)
            with d2:
                spathios_fee = st.number_input(
                    "Fee %", min_value=0.00, max_value=20.00, value=14.5
                )

        submit = st.form_submit_button("Add")
    if vat_included:
        price_per_person = price_per_person / (1 + general_vat)
    if submit:
        st.session_state["line"].append(
            [
                service_type,
                num_people,
                price_per_person,
                currency,
                discount,
                spathios_fee,
                vat[service_type],
                pricing_type,
            ]
        )


def write_lines():

    i = 0
    st.write("")

    e1, e11, e12, e13, e14, e3 = st.columns([29, 18, 18, 18, 18, 11])
    with e1:
        st.write("**Product provider:**")
    with e11:
        st.write("**Processing fee:**")
    with e12:
        st.write("**Subtotal:**")
    with e13:
        st.write("**Vat:**")
    with e14:
        st.write("**Total:**")

    st.divider()
    subtotal = 0
    vat_total = 0
    total = 0
    agg_host_cost = 0
    agg_plat_fee = 0
    agg_subtotal = 0
    agg_total = 0
    agg_vat = 0
    for line in st.session_state["line"]:

        e1, e11, e12, e13, e14, e3 = st.columns([29, 18, 18, 18, 18, 11])

        line_total = int(line[1] * line[2] * (1 + line[6]) * 100) / 100
        line_subtotal = int(line[1] * line[2] * 100) / 100
        line_plat_fee = int(line_subtotal * MANAGEMENT_FEE * 100) / 100
        line_host_cost = int(line_subtotal * (1 - MANAGEMENT_FEE) * 100) / 100
        line_vat = int((line_total - line_subtotal) * 100) / 100
        with e1:  # Type and num people
            if line[1] > 1:
                st.write(line[0] + " - " + str(line[1]) + " People")
            else:
                st.write(line[0])
        with e3:  # Delete button
            if st.button("(X)", key=i):
                del st.session_state["line"][i]
                st.experimental_rerun()

        with e14:  # Total

            st.write(str(line_total) + " " + line[3][-1])

        with e11:  # Processing fee
            st.write(str(line_plat_fee) + " " + line[3][-1])
        with e12:  # Subtotal
            st.write(str(line_subtotal) + " " + line[3][-1])
        with e13:  # VAT
            st.write(str(line_vat) + " " + line[3][-1])

        if line[7] == "by number of people":
            if line[4] == 0:
                st.markdown(
                    "<sub><em>   Price per person: "
                    + str(int(line_host_cost / line[1] * 100) / 100)
                    + " "
                    + line[3][-1]
                    + " - Fee: "
                    + str(line[5])
                    + "% - VAT: "
                    + str(line[6] * 100)
                    + "%</em></sub>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<sub><em>   Price per person: "
                    + str(int(line_host_cost / line[1] * 100) / 100)
                    + " "
                    + line[3][-1]
                    + " - Discount: "
                    + str(line[4])
                    + "\% - Fee: "
                    + str(line[5])
                    + "% - VAT: "
                    + str(line[6] * 100)
                    + "%</em></sub>",
                    unsafe_allow_html=True,
                )
        if line[7] == "by hour":
            if line[4] == 0:
                st.markdown(
                    "<sub><em>   Price per hour: "
                    + str(int(line_host_cost / line[1] * 100) / 100)
                    + " "
                    + line[3][-1]
                    + " - Fee: "
                    + str(line[5])
                    + "% - VAT: "
                    + str(line[6] * 100)
                    + "%</em></sub>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<sub><em>   Price per hour: "
                    + str(int(line_host_cost / line[1] * 100) / 100)
                    + " "
                    + line[3][-1]
                    + " - Discount: "
                    + str(line[4])
                    + "\% - Fee: "
                    + str(line[5])
                    + "% - VAT: "
                    + str(line[6] * 100)
                    + "%</em></sub>",
                    unsafe_allow_html=True,
                )
        elif line[7] == "fixed price":
            if line[4] == 0:
                st.markdown(
                    "<sub><em>   Price: "
                    + str(int(line_host_cost / line[1] * 100) / 100)
                    + " "
                    + line[3][-1]
                    + " - Fee: "
                    + str(line[5])
                    + "% - VAT: "
                    + str(line[6] * 100)
                    + "%</em></sub>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<sub><em>   Price: "
                    + str(int(line_host_cost / line[1] * 100) / 100)
                    + " "
                    + line[3][-1]
                    + " - Discount: "
                    + str(line[4])
                    + "% - Fee: "
                    + str(line[5])
                    + "% - VAT: "
                    + str(line[6] * 100)
                    + "%</em></sub>",
                    unsafe_allow_html=True,
                )
        agg_host_cost = agg_host_cost + line_host_cost
        agg_plat_fee = agg_plat_fee + line_plat_fee
        agg_subtotal = agg_subtotal + line_subtotal
        agg_total = agg_total + line_total
        agg_vat = int((agg_total - agg_subtotal) * 100) / 100
        st.divider()
        i = i + 1
    if len(st.session_state["line"]) > 0:
        f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
        with f3:
            st.markdown(
                "<h6>Subtotal: " + "</h6>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<h6>VAT: " + "</h6>",
                unsafe_allow_html=True,
            )
            st.divider()
            st.markdown(
                "<h5>Total: " + "</h5>",
                unsafe_allow_html=True,
            )
        with f4:
            st.markdown(
                "<h6>"
                + str(agg_subtotal)
                + " "
                + st.session_state["line"][0][3][-1]
                + "</h6>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<h6>"
                + str(agg_vat)
                + " "
                + st.session_state["line"][0][3][-1]
                + "</h6>",
                unsafe_allow_html=True,
            )

            st.divider()
            st.markdown(
                "<h5>"
                + str(agg_total)
                + " "
                + st.session_state["line"][0][3][-1]
                + "</h5>",
                unsafe_allow_html=True,
            )


def main():
    init_session()

    st.write("")
    st.write("")
    st.write("")
    #st.markdown(
    #    "<div style='text-align:right;'>|</div>", unsafe_allow_html=True
    #)
    leftm, margin, rightm ,totr= st.columns([1, 32, 11,1])
    with margin:
        foot = f"""
        <div style="
            position: fixed;
            bottom: 0;
            left: 25%;
            right: 0;
            width: 50%;
            padding: 0px 0px;
            text-align: center;
        ">
            <p>Spathios</p>
        </div>
        """
        # st.markdown(foot, unsafe_allow_html=True)
        # Add custom CSS
        t1, t2 = st.columns([10, 4])
        with t1:
            st.markdown(
                """
                <style>
                
                #MainMenu {visibility: visible;
                # }
                    footer {visibility: hidden;
                    }
                    .css-card {
                        border-radius: 0px;
                        padding: 30px 10px 10px 10px;
                        background-color: #f8f9fa;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                        margin-bottom: 10px;
                        font-family: "IBM Plex Sans", sans-serif;
                    }
                    
                    .card-tag {
                        border-radius: 0px;
                        padding: 1px 5px 1px 5px;
                        margin-bottom: 10px;
                        position: absolute;
                        left: 0px;
                        top: 0px;
                        font-size: 0.6rem;
                        font-family: "IBM Plex Sans", sans-serif;
                        color: white;
                        background-color: green;
                        }
                        
                    .css-zt5igj {left:0;
                    }
                    
                    span.css-10trblm {margin-left:0;
                    }
                    
                    div.css-1kyxreq {margin-top: -40px;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )
            st.image("https://app.spathios.com/images/spathios_logo.svg")
        with t2:
            st.write("")
            st.write(
                "<div style='text-align:right;'>Invoice Number</div>",
                unsafe_allow_html=True,
            )
            st.text_input(
                "Invoice Number",
                placeholder="Add the Invoice Number here",
                label_visibility="collapsed",
            )
        st.divider()
    leftm, rec, pag, rightm,totr = st.columns([1, 12, 20, 11,1])
    with rec:
        st.write(
            """To: Spathioslink 14 S.L.

B67599241

Carrer del Doctor Francesc Darder, 8-10,3º 2ª A, 08034, Barcelona                          
"""
        )
    
        text, answ = st.columns([5, 15])
        with text:
            st.write("Concept:")
        with answ:
            st.text_input(
                "Concept", label_visibility="collapsed", placeholder="Concept"
            )

    with pag:
        text, answ = st.columns([2, 8])
        with text:

            st.write("From: ")
            st.write("")
            st.write("CIF/NIF: ")
            st.write("")
            st.write("Address: ")
            st.write("")
            st.write("Date: ")
        with answ:
            st.text_input("From", label_visibility="collapsed", placeholder="From")
            st.text_input(
                "CIF/NIF", label_visibility="collapsed", placeholder="CIF/NIF"
            )
            st.text_input(
                "Address", label_visibility="collapsed", placeholder="Address"
            )
            st.text_input("Date", label_visibility="collapsed", placeholder="Date")
    leftm, margin, rightm = st.columns([1, 32, 12])
    with margin:
        with st.expander("Add line"):
            st.write(
                f"""
        <center><div style="display: flex; align-items: center; margin-left: 0;">
            <h2 style="display: inline-block;">Invoice Generator</h2>
            <sub style="margin-left:55px;font-size:small; color: green;">   beta</sub>
        </div></center>
        """,
                unsafe_allow_html=True,
            )
            ############### Main start

            add_line()
        write_lines()


if __name__ == "__main__":
    main()
